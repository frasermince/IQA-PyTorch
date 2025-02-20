import torch

from collections import OrderedDict
from pyiqa.default_model_configs import DEFAULT_CONFIGS
from pyiqa.utils.registry import ARCH_REGISTRY
from pyiqa.utils.img_util import imread2tensor

from pyiqa.losses.loss_util import weight_reduce_loss


class InferenceModel(torch.nn.Module):
    """Common interface for quality inference of images with default setting of each metric."""

    def __init__(
            self,
            metric_name,
            as_loss=False,
            loss_weight=None,
            loss_reduction='mean',
            device=None,
            **kwargs  # Other metric options
    ):
        super(InferenceModel, self).__init__()

        self.metric_name = metric_name

        # ============ set metric properties ===========
        self.lower_better = DEFAULT_CONFIGS[metric_name].get('lower_better', False)
        self.metric_mode = DEFAULT_CONFIGS[metric_name].get('metric_mode', None)
        if self.metric_mode is None:
            self.metric_mode = kwargs.pop('metric_mode')
        elif 'metric_mode' in kwargs:
            kwargs.pop('metric_mode')

        if device is None:
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        else:
            self.device = device

        self.as_loss = as_loss
        self.loss_weight = loss_weight
        self.loss_reduction = loss_reduction

        # =========== define metric model ===============
        net_opts = OrderedDict()
        # load default setting first
        if metric_name in DEFAULT_CONFIGS.keys():
            default_opt = DEFAULT_CONFIGS[metric_name]['metric_opts']
            net_opts.update(default_opt)
        # then update with custom setting
        net_opts.update(kwargs)
        network_type = net_opts.pop('type')
        self.net = ARCH_REGISTRY.get(network_type)(**net_opts)
        self.net = self.net.to(self.device)
        self.net.eval()

    def to(self, device):
        self.net.to(device)
        self.device = torch.device(device)
        return self

    def forward(self, target, ref=None):

        with torch.set_grad_enabled(self.as_loss):

            if 'fid' in self.metric_name:
                output = self.net(target, ref, device=self.device)
            else:
                if not torch.is_tensor(target):
                    target = imread2tensor(target, rgb=True)
                    target = target.unsqueeze(0)
                    if self.metric_mode == 'FR':
                        assert ref is not None, 'Please specify reference image for Full Reference metric'
                        ref = imread2tensor(ref, rgb=True)
                        ref = ref.unsqueeze(0)

                if self.metric_mode == 'FR':
                    output = self.net(target.to(self.device), ref.to(self.device))
                elif self.metric_mode == 'NR':
                    output = self.net(target.to(self.device))

        if self.as_loss:
            if isinstance(output, tuple):
                output = output[0]
            return weight_reduce_loss(output, self.loss_weight, self.loss_reduction)
        else:
            return output
