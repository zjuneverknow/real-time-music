from backend.services.va_to_music_feature import create_va_to_music_converter
import matplotlib.pyplot as plt
import numpy as np
results = {
    "tempo": [],
    "density": [],
    "mean_pitch": [],
    "brightness": [],
    "volatility": [],
    "pitch_range": [],
    "wetness": [],
}
converter = create_va_to_music_converter()
for valence_mean in np.arange(1,10,0.1):
    valence_mean = valence_mean
    for arousal_mean in np.arange(1,10, 0.1):
        arousal_mean = arousal_mean
        result = converter(
            valence_mean=valence_mean,
            arousal_mean=arousal_mean,
            seed=42,
        )
        results["tempo"].append(result["tempo"])
        results["density"].append(result["density"])
        results["mean_pitch"].append(result["mean_pitch"])
        results["brightness"].append(result["brightness"])
        results["volatility"].append(result["volatility"])
        results["pitch_range"].append(result["pitch_range"])
        results["wetness"].append(result["wetness"])


print("brightness: ", max(results["brightness"]), "min: ", min(results["brightness"]))
print("density: ", max(results["density"]), "min: ", min(results["density"]))
print("mean_pitch: ", max(results["mean_pitch"]), "min: ", min(results["mean_pitch"]))
print("volatility: ", max(results["volatility"]), "min: ", min(results["volatility"]))
print("pitch_range: ", max(results["pitch_range"]), "min: ", min(results["pitch_range"]))
print("wetness: ", max(results["wetness"]), "min: ", min(results["wetness"]))

plt.plot(results["brightness"])
plt.show()
plt.plot(results["density"])
plt.show()
plt.plot(results["mean_pitch"])
plt.show()
plt.plot(results["volatility"])
plt.show()
plt.plot(results["pitch_range"])
plt.show()
plt.plot(results["wetness"])
plt.show()