from TensorflowToolbox.utility import file_io
import cv2
import numpy as np


def norm_image(img):
    img = (img - np.min(img)) / (np.max(img) - np.min(img))
    return img

def opencv_plot(desmap_name, mask):
    desmap = np.fromfile(desmap_name, np.float32)
    desmap= np.expand_dims(np.reshape(desmap, (227, 227)), 2)
    desmap = cen_crop(desmap, (224,224))
    desmap = np.squeeze(desmap)

    desmap *= 30.0
    desmap[desmap >1 ] = 1
    desmap *= mask
    desmap = norm_image(desmap) * 255
    
    desmap = desmap.astype(np.uint8)
    im_color = cv2.applyColorMap(desmap, cv2.COLORMAP_JET)
    return im_color

def cen_crop(input_image, dsize):
    h, w, c = input_image.shape
    offset_h = int((h - dsize[0])/2)
    offset_w = int((w - dsize[1])/2)
    
    input_image = input_image[offset_h:offset_h + dsize[0], offset_w:offset_w+dsize[1], :]
    return input_image

ucsd_dir = "/media/dog/data/TranCos/TranCos/TranCos/"
desmap_list = file_io.get_listfile(ucsd_dir, "infer_desmap")

for des_name in desmap_list:
    mask_name = des_name.replace(".infer_desmap", "_mask.npy" )
    mask = np.fromfile(mask_name, np.float32)
    mask = np.expand_dims(np.reshape(mask, (227, 227)), 2)
    mask = cen_crop(mask, (224,224))
    mask = np.squeeze(mask)
    
    des_gt_name = des_name.replace(".infer_desmap", ".desmap")
    desmap = opencv_plot(des_gt_name, mask)

    img_name = des_name.replace(".infer_desmap", ".jpg")
    img = cv2.imread(img_name)
    img = cen_crop(img, (224,224))
    combine_img = np.hstack((img, desmap))
    save_name = img_name.replace(".jpg", "_combine_gt.png")
    cv2.imwrite(save_name, combine_img)
