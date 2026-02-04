#  Backyard Possums Detection to Prevent Pet–Wildlife Conflicts 🦦
**End-to-end computer vision pipeline for Real-Time possums detection using motion analysis and CNN classification**



The goal of this project is to build a real-time system that detects possums from a night camera feed.
The system combines classical computer vision (background subtraction and motion detection) with a convolutional neural network trained via transfer learning.
The final solution works on a continuous live camera feed, extracts motion-based regions of interest (ROIs), classifies them using a CNN, and confirms detection using temporal consistency logic. It can be extended for smart home automation (e.g., closing dog doors or activating feeding stations).

**Computer Vision · Deep Learning · CNN (Transfer Learning) · PyTorch · OpenCV · Real-Time Detection**

## ⚠️ **Project in Progress / Work in Progress**  



**🛠 What I Did:**
- Prepared training data from backyard video footage: extracted crops of possums and non-possum motion.
- Implemented a CNN classification pipeline using **transfer learning with ResNet18**.
- Connected the model to live RTSP camera feeds for real-time detection.
- Developed a pipeline: motion detection → ROI extraction → classification → alerting.
- Designed foundations for smart home automation: opening feeding boxes or controlling dog doors (planned).


```

Data Preparation & Model Training (offline / static videos)
----------------------------------------------------------
Static video footage
      ↓
Motion detection → ROIs
      ↓
Manual labeling of ROIs
      ↓
Transforming / augmenting data
      ↓
Train CNN (ResNet18 transfer learning)
      ↓
Model ready for live feed inference


Live Detection Pipeline
----------------------
Camera feed
      ↓
Frame skipping (every N frames)
      ↓
Background subtraction (motion detection)
      ↓
ROI extraction + padding
      ↓
CNN classifier (possum / not possum, transfer learning ResNet18)
      ↓
Frame-level decision (Sliding window: last 5 frames)
      ↓
Trigger: 3/5 possum frames → STOP

```



**🔮 Future Work / Next Steps:**
- Compare **CNN vs transfer learning** performance.
- Integrate smart home automation: open feeding boxes or close dog doors.
- Implement **data logging** from the camera feed: record timestamps, number of possums detected, and their ROIs for further analysis and visualization.
- Build **analytics dashboard** to track possum visits over time.


**⚡ Technical Highlights**
- **Data pipeline:** raw video → motion-based ROI extraction → classification dataset.
- **Model:** Transfer learning using **ResNet18**, fine-tuned for possum vs non-possum.
- **Real-time detection:** OpenCV-based processing of live camera feed.
- **Sliding window logic:** Reduces false positives by confirming possum presence across multiple frames.
- **Extensible automation hooks:** Can trigger smart home devices upon possum detection 🐾.



**💡 Why it Matters to Employers** 

    This project showcases the end-to-end lifecycle of a real-world computer vision system: from noisy data acquisition and preprocessing, to model training, and integration with a live camera feed.  

- Demonstrates ability to implement **real-time detection pipelines**.  
- Shows hands-on experience in **data collection, preprocessing, and model training** under practical conditions.  
- Combines **classical computer vision, deep learning, and smart home automation concepts**.  
- Lays groundwork for **analytics and behavior tracking** of wildlife in urban environments.


---
## Problem & Motivation

Possums regularly visit the backyard at night, naturally triggering the curiosity and hunting instincts of our dog, Beau. To prevent potential attacks and injuries to both wildlife and pets, we decided to design a smart mechanism for the dog door that automatically closes when a possum is detected in the backyard, keeping the dog safely inside.

Initially, the primary goal was to provide food — a carrot — to the possum. However, this attracted mices. This led to the idea of a smart feeding box that only opens for possums. Due to ethical considerations (in Australia, it is illegal to feed wildlife continuously), this feature is currently conceptual and intended purely as a prototype for testing detection logic.

Possums visit the backyard at nigh. Detecting possums in this environment is challenging: naive motion detectors produce many false positives caused by insects, wind-driven vegetation, mice, and infrared camera noise. The main challenge is therefore to reliably identify possums in low-light conditions while minimizing false alarms.


---

## 📚 What I Learned
- End-to-end computer vision project: data collection → model → real-time integration.
- Handling noisy real-world video, small objects, and night-time detection.
- Combining classical CV (motion detection) with deep learning for efficient ROI filtering.

---
