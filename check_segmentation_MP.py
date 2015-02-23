# -*- coding: utf-8 -*-
"""
Created on Tue Feb 17 15:17:44 2015

@author: Avelino
"""

# -*- coding: utf-8 -*-
"""
Created on Tue Feb 17 15:06:13 2015

@author: ajaver
"""
#fileName = '/Volumes/Mrc-pc/GeckoVideo/CaptureTest_90pc_Ch2_16022015_174636.mjpg';
#maskFile = '/Volumes/ajaver$/GeckoVideo/Compressed/CaptureTest_90pc_Ch2_16022015_174636.hdf5';

#fileName = '/Volumes/H/GeckoVideo/20150218/CaptureTest_90pc_Ch4_18022015_230213.mjpg'
#maskFile = '/Volumes/ajaver$/GeckoVideo/Compressed/CaptureTest_90pc_Ch4_18022015_230213.hdf5';

#fileName = '/Volumes/H/GeckoVideo/20150218/CaptureTest_90pc_Ch2_18022015_230108.mjpg'
#maskFile = '/Volumes/ajaver$/GeckoVideo/Compressed/CaptureTest_90pc_Ch2_18022015_230108.hdf5';

#fileName = '/Volumes/Mrc-pc/GeckoVideo/CaptureTest_90pc_Ch4_16022015_174636.mjpg';
#maskFile = '/Volumes/ajaver$/GeckoVideo/Compressed/CaptureTest_90pc_Ch4_16022015_174636.hdf5';

#fileName = r'G:\GeckoVideo\CaptureTest_90pc_Ch4_16022015_174636.mjpg';
#maskFile = r'Z:\GeckoVideo\Compressed\CaptureTest_90pc_Ch4_16022015_174636.hdf5';


import numpy as np
import matplotlib.pylab as plt
import cv2
import subprocess as sp
import time
import os
import re
import scipy.ndimage as nd
import h5py
import multiprocessing as mp
import Queue

MAX_N_PROCESSES = mp.cpu_count()
STRUCT_ELEMENT = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9,9)) 
SAVE_FULL_INTERVAL = 15000 #~15min

#import skimage.m
class ReadVideoffmpeg:
    def __init__(self, fileName, width = -1, height = -1):
        if os.name == 'nt':
            ffmpeg_cmd = 'ffmpeg.exe'
        else:
            ffmpeg_cmd = 'ffmpeg'
        
        
        if width<=0 or height <=0:
            try:
                command = [ffmpeg_cmd, '-i', fileName, '-']
                pipe = sp.Popen(command, stdout=sp.PIPE, stderr=sp.PIPE)
                buff = pipe.stderr.read()
                
                pipe.terminate()
                dd = buff.partition('Video: ')[2].split(',')[2]
                dd = re.findall(r'\d*x\d*', dd)[0].split('x')
                self.width = int(dd[0])
                self.height = int(dd[1])
                
            except:
                print 'I could not determine the frame size from ffmpeg, introduce the values manually'
                raise
        else:
            self.width = width
            self.height = height
                
        self.tot_pix = self.width*self.width
        
        command = [ffmpeg_cmd, 
           '-i', fileName,
           '-f', 'image2pipe',
           '-vcodec', 'rawvideo', '-']
        self.pipe = sp.Popen(command, stdout = sp.PIPE, bufsize = self.tot_pix) #use a buffer size as small as possible, makes things faster
    
    def read(self):
        raw_image = self.pipe.stdout.read(self.tot_pix)
        if len(raw_image) < self.tot_pix:
            return (0, []);
        
        image = np.fromstring(raw_image, dtype='uint8')
        image = image.reshape(self.width,self.height)
        return (1, image)
    
    def release(self):
        self.pipe.stdout.flush()
        self.pipe.terminate()

def getImageROI(image):
    #if it is needed to keep the original image then use "image=getImageROI(np.copy(image))"
    
    IM_LIMX = image.shape[0]-2
    IM_LIMY = image.shape[1]-2
    MAX_AREA = 5000
    MIN_AREA = 100

    mask = cv2.adaptiveThreshold(image,1,cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV,61,15)
    [contours, hierarchy]= cv2.findContours(mask.copy(), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    badIndex = []
    for ii, contour in enumerate(contours):
        if np.any(contour==1) or np.any(contour[:,:,0] ==  IM_LIMX)\
        or np.any(contour[:,:,1] == IM_LIMY):
            badIndex.append(ii) 
        else:
            area = cv2.contourArea(contour)
            if area<MIN_AREA or area>MAX_AREA:
                badIndex.append(ii)
    for ii in badIndex:
        cv2.drawContours(mask, contours, ii, 0, cv2.cv.CV_FILLED)
    mask[0,:] = 0; mask[:,0] = 0; mask[-1,:] = 0; mask[:,-1]=0;
    mask = cv2.dilate(mask, STRUCT_ELEMENT, iterations = 3)
    image[mask==0] = 0
#    
#
#    label_im, nb_labels = nd.label(mask);
#    label_area = nd.sum(mask, label_im, range(nb_labels + 1))
#    print 'NL %i' % nb_labels
#    mask = (np.bitwise_or(label_area<100,label_area>5000))[label_im].astype(np.uint8)
#    mask = nd.binary_erosion(mask, nd.generate_binary_structure(2,2), iterations= 1,border_value=1);
#    image[mask!=0] = 0
    
    return image
    
def proccess_worker(conn, frame_number, image):
    conn.send({'frame':frame_number, 'image':getImageROI(image)})
    conn.close()

if __name__ == '__main__':
    
    vid = ReadVideoffmpeg(fileName);
    im_height = vid.height;
    im_width = vid.width;
    
#    vid = cv2.VideoCapture(fileName)
#    im_width = vid.get(cv2.cv.CV_CAP_PROP_FRAME_WIDTH)
#    im_height = vid.get(cv2.cv.CV_CAP_PROP_FRAME_HEIGHT)

    
    mask_fid = h5py.File(maskFile, "w");
    mask_dataset = mask_fid.create_dataset("/mask", (0, im_height, im_width), 
                                    dtype = "u1", maxshape = (None, im_height, im_width), 
                                    chunks = (1, im_height, im_height),#chunks = (1, im_height, im_width), 
                                    compression="gzip", 
                                    compression_opts=4,
                                    shuffle=True);
    full_dataset = mask_fid.create_dataset("/full_data", (0, im_height, im_width), 
                                    dtype = "u1", maxshape = (None, im_height, im_width), 
                                    chunks = (1, im_height, im_height),#chunks = (1, im_height, im_width), 
                                    compression="gzip", 
                                    compression_opts=9,
                                    shuffle=True);
    full_dataset.attrs['save_interval'] = SAVE_FULL_INTERVAL
# 
                                

    proc_queue = Queue.Queue()
    frame_number = 0;
    tic_first = time.time()
    tic = tic_first
    
    while 1:#frame_number < 2:
        ret, image = vid.read()
        #image = image[:,:,1]
        if ret == 0:
            break
        image_dum = image.copy()
        frame_number += 1;
        
        if frame_number%25 == 0:
            toc = time.time()
            print frame_number, toc-tic
            tic = toc
        
        if (frame_number)%1000 == 1:
            mask_dataset.resize(frame_number + 1000, axis=0); 
        
        if frame_number % SAVE_FULL_INTERVAL== 1:
            full_dataset.resize(frame_number, axis=0); 
            full_dataset[np.floor(frame_number/SAVE_FULL_INTERVAL),:,:] = image
        
        #mask_dataset[frame_number-1,:,:] = image_dum
        #mask_dataset[frame_number-1,:,:] = getImageROI(image)
        
        parent_conn, child_conn = mp.Pipe();
        p = mp.Process(target = proccess_worker, args=(parent_conn, frame_number, image));
        p.start();
        proc_queue.put((child_conn, p))
        
        if proc_queue.qsize() >= MAX_N_PROCESSES:
            dd = proc_queue.get();
            data = dd[0].recv() #read pipe
            dd[1].join() #wait for the proccess to be completed
            
            mask_dataset[data['frame']-1,:,:] = data['image'];
            
    if mask_dataset != frame_number:
        mask_dataset.resize(frame_number, axis=0); 
    
    for x in range(proc_queue.qsize()):
        dd = proc_queue.get();
        data = dd[0].recv()
        dd[1].join()
        mask_dataset[data['frame']-1,:,:] = data['image'];

    
    
    vid.release() 
    mask_fid.close()
    
##    print 'TOTAL TIME: ', time.time()-tic_first 
#    plt.figure()
#    plt.imshow(dd, interpolation='none', cmap= 'gray')
