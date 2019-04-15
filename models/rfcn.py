import torch
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.autograd import Variable

from resnets import resnet50
from rpn import RPN

INPUT_CHANNELS_RPN = 2048
ANCHOR_SIZES = [(128, 128), (256, 128), (128, 256), (256, 256), (256, 512), (512, 256)]
STRIDE = 1
IMAGE_VS_FEATURE_SCALE = 3

class _RFCN(nn.Module):
    """ R-FCN """
    def __init__(self, num_classes=2):
        super(_RFCN, self).__init__()
        self.n_classes = num_classes

        # Initialize two types of losses
        self.RCNN_loss_cls = 0
        self.RCNN_loss_bbox = 0

        # Initialize the base feature extraction ResNet
        self.feature_extractor = resnet50(pretrained=True)

        # Modify ResNet by removing last layer and avg pooling
        self.feature_extractor = torch.nn.Sequential(*(list(self.feature_extractor.children())[:-1]))
        print(self.feature_extractor)

        # Define the RPN
        self.RCNN_rpn = RPN(INPUT_CHANNELS_RPN, ANCHOR_SIZES, STRIDE, IMAGE_VS_FEATURE_SCALE)

        # TODO: Define the pooling layers

    def forward(self, image, image_metadata, gt_boxes, num_boxes):
        batch_size = image.size(0)

        image_metadata = image_metadata.data
        gt_boxes = gt_boxes.data
        num_boxes = num_boxes.data
        self.batch_size = image.size(0)

        # feed image data to base model to obtain base feature map
        base_feat = self.feature_extractor(image)

        # feed base feature map tp RPN to obtain rois
        rois, rpn_loss_cls, rpn_loss_bbox = self.RCNN_rpn(base_feat, image_metadata, gt_boxes, num_boxes)

        # if it is training phrase, then use ground trubut bboxes for refining
        if self.training:
            roi_data = self.RCNN_proposal_target(rois, gt_boxes, num_boxes)
            rois, rois_label, rois_target, rois_inside_ws, rois_outside_ws = roi_data

            rois_label = Variable(rois_label.view(-1).long())
            rois_target = Variable(rois_target.view(-1, rois_target.size(2)))
            rois_inside_ws = Variable(rois_inside_ws.view(-1, rois_inside_ws.size(2)))
            rois_outside_ws = Variable(rois_outside_ws.view(-1, rois_outside_ws.size(2)))
        else:
            rois_label = None
            rois_target = None
            rois_inside_ws = None
            rois_outside_ws = None
            rpn_loss_cls = 0
            rpn_loss_bbox = 0

    def _init_weights(self):
        def normal_init(m, mean, stddev, truncated=False):
            """
            weight initalizer: truncated normal and random normal.
            """
            # x is a parameter
            if truncated:
                m.weight.data.normal_().fmod_(2).mul_(stddev).add_(mean) # not a perfect approximation
            else:
                m.weight.data.normal_(mean, stddev)
                if m.bias is not None:
                    m.bias.data.zero_()

        normal_init(self.RCNN_rpn.RPN_Conv, 0, 0.01, cfg.TRAIN.TRUNCATED)
        normal_init(self.RCNN_rpn.RPN_cls_score, 0, 0.01, cfg.TRAIN.TRUNCATED)
        normal_init(self.RCNN_rpn.RPN_bbox_pred, 0, 0.01, cfg.TRAIN.TRUNCATED)

    def create_architecture(self):
        self._init_modules()
        self._init_weights()