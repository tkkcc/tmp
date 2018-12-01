import os
from pathlib import Path
import numpy as np
import torch
import torch.nn.functional as F
from skimage.color import rgb2gray

from skimage.io import imread
from torch.utils.data import Dataset

# from torchvision.transforms import Grayscale
from util import pad, pad_for_kernel, to_tensor, edgetaper, center_crop, show, center_pad


class BSD(Dataset):
    # type=['train','test','val']
    def __init__(self, type="train"):
        d = Path(f"data/BSR/BSDS500/data/images/{type}").glob("**/*")
        self.d = [i for i in d if i.is_file()]
        self.k = []
        for i in range(1, 9):
            k = imread(f"data/kernel/kernel{i}_groundtruth_kernel.png").astype(np.float32) / 255
            # crop to 13x13
            k = np.clip(k, 0, 1)
            k = center_crop(k, 13)
            k /= np.sum(k)
            self.k.append(torch.from_numpy(k))
            # or pad to 27x27
            # k = torch.from_numpy(k)
            # k = k.clamp(0, 1)
            # k = center_pad(k, 27)
            # k /= k.sum()
            # self.k.append(k)
        self.s = 0.01 * 255

    def __getitem__(self, i):
        # [img1xkernel1, img1xkernel2,...,img2xkernel1]
        g = imread(self.d[i // 8]) / 255
        g = rgb2gray(g).astype(np.float32)
        k = self.k[i % 8]
        g = torch.from_numpy(g)
        s = torch.tensor((self.s,), dtype=torch.float)
        g = g.view(1, *g.shape)
        # blur
        y = F.conv2d(g.view(1, *g.shape), k.view(1, 1, *k.shape))
        g = center_crop(g, 250)
        y = center_crop(y, 250)[0]
        # show(torch.cat((g.detach().cpu()[0], y.detach().cpu()[0,0]), 0))
        # noise
        # y += torch.randn_like(y) * s / 255
        # edgetaping, todo convert to torch, and move to model stage
        y = y.permute(1, 2, 0)
        y = to_tensor(edgetaper(pad_for_kernel(y.numpy(), k.numpy(), "edge"), k.numpy())).astype(
            np.float32
        )
        y = torch.from_numpy(y).squeeze(-1)
        # [1,250,250] [1,267,267] [1,13,13] [1]
        return g, y, k, s

    def __len__(self):
        return len(self.d) * 8

