# tnrd
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from util import show, log, parameter, gen_dct2
from scipy.io import loadmat
from config import o


class ModelStage(nn.Module):
    def __init__(self, stage=1):
        super(ModelStage, self).__init__()
        penalty_num = o.penalty_num
        self.depth = o.depth
        self.channel = channel = filter_num = o.channel
        self.filter_size = filter_size = 5
        self.basis = torch.tensor(gen_dct2(filter_size), dtype=torch.float)
        self.lam = torch.tensor(0 if stage == 1 else log(0.1), dtype=torch.float)
        self.mean = torch.linspace(-310, 310, penalty_num).view(1, 1, penalty_num, 1, 1)
        self.actw = torch.randn(1, filter_num, penalty_num, 1, 1)
        self.actw *= 10 if stage == 1 else 5 if stage == 2 else 1
        self.actw = [torch.randn(1, filter_num, penalty_num, 1, 1) for i in range(self.depth)]
        self.filter = [
            torch.randn(channel, 1, filter_size, filter_size),
            *(
                torch.randn(channel, channel, filter_size, filter_size)
                for i in range(self.depth - 1)
            ),
        ]
        self.bias = [torch.randn(channel) for i in range(self.depth)]
        self.pad = nn.ReplicationPad2d(filter_size // 2)
        self.crop = nn.ReplicationPad2d(-(filter_size // 2))
        self.lam = parameter(self.lam)
        self.bias = parameter(self.bias, o.bias_scale)
        self.filter = parameter(self.filter, o.filter_scale)
        self.actw = parameter(self.actw, o.actw_scale)

    # Bx1xHxW
    def forward(self, inputs):
        x, y, lam = inputs
        x *= 255
        y *= 255
        xx = x
        self.mean = self.mean.to(x.device)
        self.basis = self.basis.to(x.device)
        f = self.filter
        t = []
        for i in range(self.depth):
            x = F.conv2d(self.pad(x), f[i], self.bias[i])
            t.append(x)
            x = (((x.unsqueeze(2) - self.mean).pow(2) / -200).exp() * self.actw[i]).sum(2)
        x = self.crop(F.conv_transpose2d(x, f[self.depth - 1]))
        for i in reversed(range(self.depth - 1)):
            c1 = t[i].unsqueeze(2)
            x = x * (
                ((c1 - self.mean).pow(2) / -200).exp() * (c1 - self.mean) / -100 * self.actw[i]
            ).sum(2)
            x = self.crop(F.conv_transpose2d(x, f[i]))
        return (xx - (x + self.lam.exp() * (xx - y))) / 255


class ModelStack(nn.Module):
    def __init__(self, stage=1, weight=None):
        super(ModelStack, self).__init__()
        self.m = nn.ModuleList(ModelStage(i + 1) for i in range(stage))
        pad_width = self.m[0].filter_size + 1
        self.pad = nn.ReplicationPad2d(pad_width)
        self.crop = nn.ReplicationPad2d(-pad_width)
        self.stage = stage

    def forward(self, d):
        # tnrd pad and crop
        # x^t, y=x^0, s
        d[1] = self.pad(d[1])
        for i in self.m:
            d[0] = self.pad(d[0])
            d[0] = i(d)
            d[0] = self.crop(d[0])
        return d[0]
