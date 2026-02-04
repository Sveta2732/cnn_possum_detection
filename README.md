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

## ⚠️ Key Challenges

- **Night footage with strong noise and low contrast** – limited visibility and IR artifacts make possum detection harder. 

-  **High number of false motion triggers** – insects, shadows, rain, vegetation, mice, and wind generate many non-possum ROIs. 

-  **Highly imbalanced data** – few possum appearances vs many non-possum motions make training CNNs challenging.  

-  **Strong similarity between consecutive frames** – frames from the same night are often almost identical, leading to redundant ROIs.  

-  **Continuous camera feed** – very large number of ROIs need to be processed by the CNN in real time.  

-  **Low possum movement** – possums may remain still for long periods, making motion-based detection unreliable.  

-  **ROI quality variability** – crops can be partial, occluded, or poorly illuminated, complicating CNN classification.  

- **Manual labeling constraints** – creating representative non-possum and possum datasets is time-consuming and labor-intensive.  
---

## ✂️ Data Collection & Preparation

Data was collected directly from night camera recordings, not live feed.  

Motion detection was used to automatically generate **Regions of Interest (ROIs)**, which were then manually reviewed, sorted, and labeled.  

#### Data Handling Decisions:

-  **Session-based splitting:** ROIs from the same night session were kept together in either **train** or **test** sets.  
    - Reason: consecutive frames are highly similar, splitting them could cause **data leakage**.  

-  **Padding-based resizing:** ROIs were resized to 224×224 using padding to preserve object proportions.  
    - Reason: standard resizing or cropping would distort possum features.  
 
 -  **Inclusion of motion-blurred images:**  
    - Even though some possum images were blurry due to movement, they were kept in training to reflect realistic scenarios.  
    - This helps the model learn to detect possums in natural night conditions, not just ideal still images.  

 

#### Example ROIs

#### Example ROIs

**Good possum images :**  

|  ![good3](https://raw.githubusercontent.com/Sveta2732/cnn_possum_detection/54aa149d1b348b02d1058297e43970be421a2b38/images/good%20possum%20(2).jpg) | ![good4](https://raw.githubusercontent.com/Sveta2732/cnn_possum_detection/54aa149d1b348b02d1058297e43970be421a2b38/images/good%20possum.jpg) |![good1](https://raw.githubusercontent.com/Sveta2732/cnn_possum_detection/54aa149d1b348b02d1058297e43970be421a2b38/images/good_possum.jpg) | ![good2](https://raw.githubusercontent.com/Sveta2732/cnn_possum_detection/54aa149d1b348b02d1058297e43970be421a2b38/images/good%20possum%20(3).jpg) |
|--------------------------------------|--------------------------------------|--------------------------------------|--------------------------------------|

**Blurry / Bad possum images :**  

|  ![bad2](https://raw.githubusercontent.com/Sveta2732/cnn_possum_detection/54aa149d1b348b02d1058297e43970be421a2b38/images/bad%20possum%20(4).jpg) | ![bad1](https://raw.githubusercontent.com/Sveta2732/cnn_possum_detection/54aa149d1b348b02d1058297e43970be421a2b38/images/bad%20possum.jpg) |![bad3](https://raw.githubusercontent.com/Sveta2732/cnn_possum_detection/54aa149d1b348b02d1058297e43970be421a2b38/images/bad%20possum%20(3).jpg) | ![bad4](https://raw.githubusercontent.com/Sveta2732/cnn_possum_detection/54aa149d1b348b02d1058297e43970be421a2b38/images/bad%20possum%20(2).jpg) |
|--------------------------------------|--------------------------------------|--------------------------------------|--------------------------------------|

**Mice / non-possum images :**  

|![mouse2](https://raw.githubusercontent.com/Sveta2732/cnn_possum_detection/54aa149d1b348b02d1058297e43970be421a2b38/images/mouse%20(2).jpg) |  ![mouse1](https://raw.githubusercontent.com/Sveta2732/cnn_possum_detection/54aa149d1b348b02d1058297e43970be421a2b38/images/mouse.jpg) | 
|--------------------------------------|--------------------------------------|



---

## 🧠 Model

A **convolutional neural network (CNN)** was trained using **transfer learning** to distinguish possum vs non-possum ROIs.  

**Key details:**
- Pretrained backbone used; all layers frozen except the last one.
- Custom classification head trained on possum vs non-possum ROIs.
- Input: motion-based ROIs extracted from video frames.
- Batch-based training to handle many small crops efficiently.
- Inference performed per ROI in real-time.
- Combines classical motion detection with CNN classification for robust possum detection.
---

## 🎯 Detection Logic

To **reduce false positives**, a temporal decision mechanism is applied:

A possum is considered **detected** only if it appears in **at least 3 out of the last 5 processed frames**.

**Why this matters:**
- Reduces single-frame misclassifications.
- Stabilizes predictions in noisy night conditions.
- Ensures robust detection when possums move slowly or remain stationary.

---
## 🔦 Results

The system **successfully detects possums** in real night conditions.  
False positives caused by insects, wind-driven vegetation, or IR noise are significantly reduced compared to a naive motion detection approach.

**Performance metrics on test set:**

- **Best test accuracy:** 0.9974  
- **Confusion matrix:**

|             | Predicted Non-Possum | Predicted Possum |
|-------------|-------------------:|----------------:|
| Actual Non-Possum | 850                | 0               |
| Actual Possum     | 8                  | 2203            |

- **Recall:** 0.9964  
- **Precision:** 1.0  

**Key observations on real-time camera feed:**
- Model triggers **immediately when a possum appears**.
- Works **without delays** on live feed.
- Sliding window mechanism ensures **stable predictions**, even if possums pause or move slowly.

---

## 🔒 Limitations 

While the system performs well in typical night conditions, several limitations exist:

- **Adverse weather and IR noise:** Performance degrades in heavy rain, strong wind, or extreme infrared camera noise.  
- **Motion-dependent detection:** Completely static possums may be missed, as detection relies on movement.  
- **Limited dataset size:** Possums appear rarely, limiting the diversity of training examples.  
- **Camera quality and setup:** Low-resolution cameras, poor angles, or distance reduce ROI quality.  
- **Incomplete non-possum coverage:** It's impossible to capture all possible non-possum motions; the model may misclassify unseen objects as possums.

---

## 🔮 Next Moves

Currently, the system stops and prints a message when a possum is detected. Planned improvements include:

- **Possum analytics:** Instead of exiting, the system will log detections with:
  - Timestamp  
  - ROI crops 
  - Bounding boxes (Location in the backyard)
  This data will enable graphs and analysis of possum activity over time.

- **Smart home integration:** Connect detection to devices such as:
  - Automatic feeding box 🥕 *(prototype to test functionality; possums will **not be fed constantly**)*  
  - Dog door lock mechanism 🚪  
  The system will trigger these devices when a possum is detected.

- **Model experimentation:** Train a **standard CNN from scratch** without transfer learning to compare performance with the current ResNet18-based transfer learning model.

- 🎯 **Overall goal:** Gain **practical experience with CNNs**, improve **real-time detection reliability**, and build a **functional prototype for backyard wildlife management** and analytics.

---

## 📚 What I Learned
- Full lifecycle of a computer vision project: from data collection and preprocessing → CNN training → real-time integration with live camera feed.
- Tackling noisy night-time video, detecting small moving objects, and designing robust detection pipelines.
- Combining classical computer vision (motion detection, ROI extraction) with deep learning to efficiently filter and classify objects.
- Applying **machine learning techniques to real-world problems**, turning everyday challenges (backyard wildlife management) into actionable, coded solutions.
- Strengthened skills in **problem-solving with ML**, demonstrating how to leverage models not just for theory, but to solve concrete, real-life challenges through code and intelligent systems.


---
