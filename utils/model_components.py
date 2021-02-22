import tensorflow as tf
import numpy as np
from tensorflow.keras.models import Model
import utils.korean_manager as korean_manager
import utils.CustomLayers as CustomLayers

def build_FC(input_image,x,settings):
    if settings['iterative_refinement']==True:
        preds=build_ir_split(input_image,x,settings)
        return Model(inputs=input_image,outputs=preds)

    if settings['split_components']:
        CHO,JUNG,JONG=build_FC_split(x,settings)
        return Model(inputs=input_image,outputs=[CHO,JUNG,JONG])
    else:
        x=build_FC_regular(x)
        return Model(inputs=input_image,outputs=x)

def build_FC_split(x,settings):
    if settings['fc_link']=='':
        x=tf.keras.layers.Flatten()(x)
    elif settings['fc_link']=='GAP':
        x=tf.keras.layers.GlobalAveragePooling2D()(x)
    elif settings['fc_link']=='GWAP':
        x=CustomLayers.GlobalWeightedAveragePooling()(x)
    #x=tf.keras.layers.Dense(1024)(x)

    CHO=tf.keras.layers.Dense(len(korean_manager.CHOSUNG_LIST),activation='softmax',name='CHOSUNG')(x)
    JUNG=tf.keras.layers.Dense(len(korean_manager.JUNGSUNG_LIST),activation='softmax',name='JUNGSUNG')(x)
    JONG=tf.keras.layers.Dense(len(korean_manager.JONGSUNG_LIST),activation='softmax',name='JONGSUNG')(x)
    return CHO,JUNG,JONG

def build_ir_split(input_image,x,settings):
    units=512
    _,width,height,channels=x.shape
    x=tf.keras.layers.Reshape((width*height,channels))(x)
    #Define attention + GRU for each component
    CHO_RNN=CustomLayers.RNN_Decoder(units,len(korean_manager.CHOSUNG_LIST))
    JUNG_RNN=CustomLayers.RNN_Decoder(units,len(korean_manager.JUNGSUNG_LIST))
    JONG_RNN=CustomLayers.RNN_Decoder(units,len(korean_manager.JONGSUNG_LIST))

    #Build RNN by looping the decoder t times
    zero_list=tf.tile(tf.zeros_like(input_image)[:,0:1,1],tf.constant([1,512]))
    hidden_CHO, hidden_JUNG, hidden_JONG = zero_list,zero_list,zero_list
    pred_list=[]

    for timestep in range(settings['refinement_t']):
        pred_CHO, hidden_CHO,_ = CHO_RNN(x, hidden_CHO)
        pred_JUNG, hidden_CHO,_ = JUNG_RNN(x, hidden_JUNG)
        pred_JONG, hidden_CHO,_ = JONG_RNN(x, hidden_JONG)

        if not timestep==settings['refinement_t']:
            index=str(timestep)
        else:
            index=''
        pred_CHO._name='CHOSUNG'+index
        pred_JUNG._name='JUNGSUNG'+index
        pred_JONG._name='JONGSUNG'+index
        pred_list+=[pred_CHO,pred_JUNG,pred_JONG]

    return pred_list

def build_FC_regular(x):
    x=tf.keras.layers.Flatten()(x)
    x=tf.keras.layers.Dense(1024)(x)
    x=tf.keras.layers.Dense(len(korean_manager.load_charset()),activation='softmax',name='output')(x)
    return x

def PreprocessingPipeline(direct_map):
    preprocessing=tf.keras.models.Sequential()

    #[0, 255] to [0, 1] with black white reversed
    preprocessing.add(tf.keras.layers.experimental.preprocessing.Rescaling(scale=-1/255,offset=1))
    #DirectMap normalization
    if direct_map==True:
        preprocessing.add(DirectMapGeneration())
    return preprocessing

def DirectMapGeneration():
    #Generate sobel filter for 8 direction maps
    sobel_filters=[
        [[-1,0,1],
        [-2,0,2],
        [-1,0,1]],

        [[1,0,-1],
        [2,0,-2],
        [1,0,-1]],

        [[1,2,1],
        [0,0,0],
        [-1,-2,-1]],

        [[-1,-2,-1],
        [0,0,0],
        [1,2,1]],

        [[0,1,2],
        [-1,0,1],
        [-2,-1,0]],

        [[0,-1,-2],
        [1,0,-1],
        [2,1,0]],

        [[-2,-1,0],
        [-1,0,1],
        [0,1,2]],

        [[2,1,0],
        [1,0,-1],
        [0,-1,-2]]]
    sobel_filters=np.array(sobel_filters).astype(np.float).reshape(8,3,3,1)
    sobel_filters=np.moveaxis(sobel_filters, 0, -1)

    DirectMap = tf.keras.models.Sequential()
    DirectMap.add(tf.keras.layers.Conv2D(8, (3,3), padding='same',input_shape=(None, None, 1),use_bias=False))
    DirectMap.set_weights([sobel_filters])
    return DirectMap