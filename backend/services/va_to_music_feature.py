from pathlib import Path

import joblib
import numpy as np


DEFAULT_MODEL_PATH = Path(__file__).resolve().parents[1] / "model" / "va_to_music" / "music_va_gmm_v2.pkl"
INPUT_COLS = ["valence_mean", "arousal_mean"]
NON_NEGATIVE_FEATURES = {
    "tempo",
    "density",
    "mean_pitch",
    "brightness",
    "volatility",
    "pitch_range",
    "wetness",
}


def _gaussian_log_pdf(x, mean, covariance):
    dim = x.shape[0]
    regularized_cov = covariance + np.eye(dim) * 1e-6
    diff = x - mean
    sign, logdet = np.linalg.slogdet(regularized_cov)
    if sign <= 0:
        raise np.linalg.LinAlgError("Covariance matrix is not positive definite.")

    mahalanobis = diff @ np.linalg.solve(regularized_cov, diff)
    return -0.5 * (dim * np.log(2 * np.pi) + logdet + mahalanobis)


def _postprocess_sample(sampled):
    processed = {}
    for name, value in sampled.items():
        if name in NON_NEGATIVE_FEATURES:
            value = max(0.0, float(value))
        if name == "pitch_range":
            value = float(round(value))
        processed[name] = value
    return processed


def load_va_music_model(model_path=DEFAULT_MODEL_PATH):
    model_path = Path(model_path)
    if not model_path.exists():
        raise FileNotFoundError(f"Model file not found: {model_path}")

    model_data = joblib.load(model_path)
    return (
        model_data["gmm_model"],
        model_data["data_scaler"],
        model_data["feature_names"],
    )


def va_to_music_features(
    valence_mean,
    arousal_mean,
    model,
    scaler,
    feature_names,
    seed=None,
    temperature=0.1,
    deterministic_component=True,
):
    if temperature <= 0:
        raise ValueError("temperature must be greater than 0")

    rng = np.random.default_rng(seed)
    input_values = np.array([valence_mean, arousal_mean], dtype=float)
    input_dim = len(INPUT_COLS)
    scaled_input = (input_values - scaler.mean_[:input_dim]) / scaler.scale_[:input_dim]

    input_idx = list(range(input_dim))
    output_idx = list(range(input_dim, len(feature_names)))

    log_weights = []
    for comp in range(model.n_components):
        mu = model.means_[comp]
        cov = model.covariances_[comp]
        mu_input = mu[input_idx]
        cov_input = cov[np.ix_(input_idx, input_idx)]
        log_prior = np.log(model.weights_[comp] + 1e-12)
        log_likelihood = _gaussian_log_pdf(scaled_input, mu_input, cov_input)
        log_weights.append(log_prior + log_likelihood)

    log_weights = np.array(log_weights)
    log_weights -= np.max(log_weights)
    weights = np.exp(log_weights)
    weights /= weights.sum()

    if deterministic_component:
        component_index = int(np.argmax(weights))
    else:
        component_index = int(rng.choice(model.n_components, p=weights))

    mu = model.means_[component_index]
    cov = model.covariances_[component_index]

    mu_input = mu[input_idx]
    mu_output = mu[output_idx]
    cov_ii = cov[np.ix_(input_idx, input_idx)]
    cov_io = cov[np.ix_(input_idx, output_idx)]
    cov_oi = cov[np.ix_(output_idx, input_idx)]
    cov_oo = cov[np.ix_(output_idx, output_idx)]

    inv_cov_ii = np.linalg.inv(cov_ii + np.eye(len(input_idx)) * 1e-6)
    cond_mu = mu_output + cov_oi @ inv_cov_ii @ (scaled_input - mu_input)
    cond_cov = cov_oo - cov_oi @ inv_cov_ii @ cov_io
    cond_cov += np.eye(len(output_idx)) * 1e-6

    scaled_sample = rng.multivariate_normal(cond_mu, cond_cov * temperature)
    full_sample_scaled = np.concatenate([scaled_input, scaled_sample])
    full_sample_original = scaler.inverse_transform(full_sample_scaled.reshape(1, -1))[0]

    output_feature_names = feature_names[input_dim:]
    output_values = full_sample_original[input_dim:]
    return _postprocess_sample(dict(zip(output_feature_names, output_values)))


def create_va_to_music_converter(model_path=DEFAULT_MODEL_PATH):
    """
    创建一个 VA -> 音乐特征 的转换器。

    参数
    ----------
    model_path : str | Path, optional
        已训练好的 GMM 模型文件路径。
        默认值为 "model/music_va_gmm_v1.pkl"。
        该文件内部应至少包含：
        - gmm_model
        - data_scaler
        - feature_names

    返回
    -------
    convert : callable
        一个可直接调用的转换函数，签名如下：

        convert(
            valence_mean,
            arousal_mean,
            seed=None,
            temperature=0.1,
            deterministic_component=True,
        ) -> dict

    convert 输入参数说明
    --------------------
    valence_mean : float
        情绪价度（Valence）的均值，表示情绪的正负倾向。
        数值越高通常表示越积极、愉快。
        建议范围：
        - 如果你的数据沿用当前训练集标注体系：通常约为 1.0 到 9.0
        - 如果你在别的项目里做了归一化：常见为 0.0 到 1.0
        注意：
        - 最好与训练数据的标注范围保持一致，否则预测会偏移明显。

    arousal_mean : float
        情绪唤醒度（Arousal）的均值，表示情绪的激烈程度。
        数值越高通常表示越兴奋、紧张、有能量。
        建议范围：
        - 如果沿用当前训练集：通常约为 1.0 到 9.0
        - 如果使用归一化数据：常见为 0.0 到 1.0
        注意：
        - 必须与训练时使用的数据尺度一致。

    valence_std : float, optional
        Valence 的标准差，表示情绪波动程度。
        默认值为 0.0。
        建议范围：
        - >= 0
        - 在当前数据中常见约为 0.0 到 3.0
        取值越大，表示对应情绪标签更分散。

    arousal_std : float, optional
        Arousal 的标准差，表示唤醒度波动程度。
        默认值为 0.0。
        建议范围：
        - >= 0
        - 在当前数据中常见约为 0.0 到 3.0

    seed : int | None, optional
        随机种子。
        默认值为 None。
        - 传入整数时：结果可复现
        - 传入 None 时：每次采样都可能不同

    temperature : float, optional
        采样温度，用于控制输出随机性。
        默认值为 0.1。
        必须 > 0。
        建议范围：
        - 0.05 到 0.2：结果更稳定，波动较小
        - 0.2 到 0.5：保留一定多样性
        - > 0.5：结果差异可能明显变大
        经验上：
        - 越小越接近“保守生成”
        - 越大越随机

    deterministic_component : bool, optional
        是否固定使用后验概率最高的 GMM 分量。
        默认值为 True。
        - True：结果更稳定，更适合生产环境
        - False：先随机选分量，再采样，结果会更有多样性

    convert 输出
    ------------
    返回一个 dict，包含生成的音乐特征，当前通常包括：

    {
        "tempo": float,
        "density": float,
        "mean_pitch": float,
        "brightness": float,
        "volatility": float,
        "pitch_range": float,
        "wetness": float
    }

    输出字段说明
    ------------
    tempo : float
        节奏速度，通常可理解为 BPM 相关特征。
        一般应 >= 0。

    density : float
        音符/起音密度，表示单位时间内事件出现频率。
        一般应 >= 0。

    mean_pitch : float
        平均音高代理特征。
        一般应 >= 0。

    brightness : float
        明亮度代理特征，通常与高频能量相关。
        一般应 >= 0。

    volatility : float
        音高变化波动程度。
        一般应 >= 0。

    pitch_range : float
        音域范围。
        代码中通常会做四舍五入处理，结果接近整数。
        一般应 >= 0。

    wetness : float
        湿度/混响感代理特征。
        一般应 >= 0。

    使用建议
    --------
    1. 如果你想要更稳定的输出：
       - deterministic_component=True
       - temperature 设为 0.05 ~ 0.1

    2. 如果你想要更丰富的随机性：
       - deterministic_component=False
       - temperature 设为 0.2 ~ 0.4

    3. 如果迁移到别的项目：
       - 输入 VA 的量纲必须与训练集一致
       - 推荐保留同一个 scaler 和 feature_names 一起使用
    """
    model, scaler, feature_names = load_va_music_model(model_path)

    def convert(
        valence_mean,
        arousal_mean,
        seed=None,
        temperature=0.1,
        deterministic_component=True,
    ):
        return va_to_music_features(
            valence_mean=valence_mean,
            arousal_mean=arousal_mean,
            model=model,
            scaler=scaler,
            feature_names=feature_names,
            seed=seed,
            temperature=temperature,
            deterministic_component=deterministic_component,
        )

    return convert


if __name__ == "__main__":
    converter = create_va_to_music_converter()
    result = converter(
        valence_mean=0.6,
        arousal_mean=0.4,
        seed=42,
    )
    print(result)
