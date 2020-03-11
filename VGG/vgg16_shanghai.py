# -*- coding: utf-8 -*-
"""Copy of vgg16.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1v7tOraTDeK4-e8ULLA5N5GUjMlZa1aZo
"""

from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
from google.colab import auth
from oauth2client.client import GoogleCredentials

auth.authenticate_user()
gauth = GoogleAuth()
gauth.credentials = GoogleCredentials.get_application_default()
drive = GoogleDrive(gauth)

link="https://drive.google.com/open?id=1v1C9hlMp_ffTs2HxoML7-GqVtNqJiW5Z"
fluff, id = link.split('=')
downloaded = drive.CreateFile({'id':id}) 
downloaded.GetContentFile('data.zip')

!unzip ./data.zip
!mv ./ucf\ anaomaly\ detection/* ./
!rm -r ./ucf\ anaomaly\ detection

import os
from classifier import classifier_model,conv_dict,build_classifier_model,load_weights
import glob
from keras.applications.vgg16 import VGG16
from keras.applications.vgg16 import preprocess_input
import  configuration as cfg
from tqdm import tqdm
from utils.video_util import *
from utils.array_util import *
import pandas as pd
import cv2
from keras.models import Model

vgg = VGG16(weights='imagenet',include_top=True)
vgg.layers.pop()
vgg.layers.pop()
feature_extractor= Model(input=vgg.input, output=[vgg.layers[-1].output])

def generatedata(path,feature_extractor):
    x_train=[]
    y_train=[]
    for i,video_file in tqdm(enumerate(glob.glob(path))):
        video_name = os.path.basename(video_file).split('.')[0]
        frames = get_video_frames(video_file)  
        num_frames=len(frames)
        if video_name[0:6] == "Normal":
            y_train+=[0]*num_frames
        else:
            y_train+=[1]*num_frames
        for frame in frames:
            frame=cv2.resize(frame,(224,224))
            frame= frame.reshape((1, frame.shape[0], frame.shape[1], frame.shape[2]))
            frame = preprocess_input(frame)
            rgb_feature = feature_extractor.predict(frame)[0]
            x_train.append(np.array(rgb_feature))
        x_train.append(np.array([0]*4096))
        y_train.append(0)
        if i%10==0:
          np.savetxt("x_train.txt", x_train)
          np.savetxt("y_train.txt", y_train)
    x_train=np.array(x_train)
    x_train=x_train.reshape((1, x_train.shape[0], x_train.shape[1]))
    return x_train,y_train

x_train,y_train=generatedata('./training/*.mp4',feature_extractor)

x_train=np.loadtxt("x_train.txt")
x_train=np.array(x_train)
x_train=x_train.reshape((x_train.shape[0],1, x_train.shape[1]))

y_train=np.loadtxt("y_train.txt")
y_train=np.array([[x] for x in y_train])
# y_train=y_train.reshape(1,len(y_train))



from keras import backend as K
def recall_m(y_true, y_pred):
        true_positives = K.sum(K.round(K.clip(y_true * y_pred, 0, 1)))
        possible_positives = K.sum(K.round(K.clip(y_true, 0, 1)))
        recall = true_positives / (possible_positives + K.epsilon())
        return recall

def precision_m(y_true, y_pred):
        true_positives = K.sum(K.round(K.clip(y_true * y_pred, 0, 1)))
        predicted_positives = K.sum(K.round(K.clip(y_pred, 0, 1)))
        precision = true_positives / (predicted_positives + K.epsilon())
        return precision

def f1_m(y_true, y_pred):
    precision = precision_m(y_true, y_pred)
    recall = recall_m(y_true, y_pred)
    return 2*((precision*recall)/(precision+recall+K.epsilon()))

from keras import Sequential
from keras.layers import Dense, Dropout,LSTM
from keras.regularizers import l2

def classifier_model():
    model = Sequential()
    model.add(LSTM(512, input_dim=4096, kernel_initializer='glorot_normal', kernel_regularizer=l2(0.01), activation='relu'))
    model.add(Dropout(0.6))
    model.add(Dense(64, kernel_initializer='glorot_normal', kernel_regularizer=l2(0.01), activation='sigmoid'))
    model.add(Dropout(0.6))
    model.add(Dense(32, kernel_initializer='glorot_normal', kernel_regularizer=l2(0.01)))
    model.add(Dropout(0.6))
    model.add(Dense(1, kernel_initializer='glorot_normal', kernel_regularizer=l2(0.01), activation='sigmoid'))
    return model

model=classifier_model()
model.compile(loss='binary_crossentropy', optimizer='adam', metrics=['accuracy',f1_m])
model.fit(x_train,y_train,epochs=10)
model.fit

model.save_weights("model.h5")



"""###Testing the model"""



sample_video_path = './testing/*.mp4'
# read video
score_TT = 0
score_TF = 0
score_FF = 0
score_FT = 0
step = 0
real_n = 0
real_a = 0
for video_file in glob.glob(sample_video_path):
    step += 1
    print("\nStep : ",step)
    video_name = os.path.basename(video_file).split('.')[0]
    print("Video_name : ",video_name)
    if video_name[0:6] == "Normal":
        real_n += 1
    else:
        real_a += 1
    frames = get_video_frames(video_file)
    num_frames=len(frames)

    rgb_features = []
    for frame in frames:
        frame=cv2.resize(frame,(224,224))
        frame= frame.reshape((1, frame.shape[0], frame.shape[1], frame.shape[2]))
        frame = preprocess_input(frame)
        rgb_feature = feature_extractor.predict(frame)[0]
        rgb_features.append(np.array(rgb_feature))

    rgb_features = np.array(rgb_features)     
    leng,widt=rgb_features.shape
    predictions = model.predict(rgb_features.reshape(leng,1,widt))
    predictions = np.array(predictions).squeeze()

    if max(predictions)> 0.5:
        print("*** anomaly video ***")
        if video_name[0:6] == "Normal":
            score_TF += 1
        else:
            score_FF += 1
    else:
        if video_name[0:6] == "Normal":
            score_TT += 1
        else:
            score_FT += 1
        print(' ** Normal video ** ')
print("Number of Video files = ",step)
print("Number of Actual-Normal-Videos = ",real_n,"Number of Predicted Normal Videos = ",score_TT + score_FT)
print("Number of Actual-Anomaly Videos = ",real_a,"Number of Predicted Anomaly Videos = ",score_TF + score_FF)
print(" ** Accuaracy of Prediction ** ")
if real_n!=0:
    print(" TT = ",round(score_TT/real_n,2),"TF = ",round(score_TF/real_n,2))
if real_a!=0:
    print(" FT = ",round(score_FT/real_a,2),"FF = ",round(score_FF/real_a,2))



