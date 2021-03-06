# TorchIO

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.3598622.svg)](https://doi.org/10.5281/zenodo.3598622)
[![PyPI version](https://badge.fury.io/py/torchio.svg)](https://badge.fury.io/py/torchio)
[![Build Status](https://travis-ci.org/fepegar/torchio.svg?branch=master)](https://travis-ci.org/fepegar/torchio)


`torchio` is a Python package containing a set of tools to efficiently
read, sample and write 3D medical images in deep learning applications
written in [PyTorch](https://pytorch.org/),
including intensity and spatial transforms
for data augmentation and preprocessing. Transforms include typical computer vision operations
such as random affine transformations and also domain specific ones such as
simulation of intensity artifacts due to
[MRI magnetic field inhomogeneity](http://mriquestions.com/why-homogeneity.html)
or [k-space motion artifacts](http://proceedings.mlr.press/v102/shaw19a.html).

This package has been greatly inspired by [NiftyNet](https://niftynet.io/).


## Credits

If you like this repository, please click on Star!

If you used this package for your research, please cite this repository using
the information available on its
[Zenodo entry](https://doi.org/10.5281/zenodo.3598622) or use this BibTeX:

```bibtex
@software{perez_garcia_fernando_2020_3598622,
  author       = {Pérez-García, Fernando},
  title        = {{fepegar/torchio: TorchIO: Tools for loading,
                   augmenting and writing 3D medical images on
                   PyTorch}},
  month        = jan,
  year         = 2020,
  publisher    = {Zenodo},
  doi          = {10.5281/zenodo.3598622},
  url          = {https://doi.org/10.5281/zenodo.3598622}
}
```


## Index

- [Installation](#installation)
- [Features](#features)
  * [Data handling](#data-handling)
    - [`ImagesDataset`](#imagesdataset)
    - [Samplers](#samplers)
    - [`Queue`](#queue)
  * [Transforms](#transforms)
    - [Augmentation](#augmentation)
      * [Intensity](#intensity)
        - [MRI k-space motion artifacts](#mri-k-space-motion-artifacts)
        - [MRI magnetic field inhomogeneity](#mri-magnetic-field-inhomogeneity)
        - [Gaussian noise](#gaussian-noise)
      * [Spatial](#spatial)
        - [B-spline dense deformation](#b-spline-dense-deformation)
        - [Flip](#flip)
        - [Affine transform](#affine-transform)
    - [Preprocessing](#preprocessing)
        * [Histogram standardization](#histogram-standardization)
        * [Z-normalization](#z-normalization)
        * [Rescale](#rescale)
        * [Resample](#resample)
        * [Pad](#pad)
        * [Crop](#crop)

- [Example](#example)
- [Related projects](#related-projects)
- [See also](#see-also)


## Installation

This package is on the
[Python Package Index (PyPI)](https://pypi.org/project/torchio/).
To install it, just run in a terminal the following command:

```shell
$ pip install torchio
```


## Features

### Data handling

#### [`ImagesDataset`](torchio/dataset/images.py)

`ImagesDataset` is a reader of medical images that directly inherits from
[`torch.utils.Dataset`](https://pytorch.org/docs/stable/data.html#torch.utils.data.Dataset).
It can be used with a
[`torch.utils.DataLoader`](https://pytorch.org/docs/stable/data.html#torch.utils.data.DataLoader)
for efficient reading and data augmentation.

It receives a list of subjects, where each subject is composed of a list of
[`torchio.Image`](torchio/dataset/images.py) instances.
The paths suffix must be `.nii`, `.nii.gz` or `.nrrd`.

```python
import torchio

subject_a = [
    Image('t1', '~/Dropbox/MRI/t1.nrrd', torchio.INTENSITY),
    Image('label', '~/Dropbox/MRI/t1_seg.nii.gz', torchio.LABEL),
]
subject_b = [
    Image('t1', '/tmp/colin27_t1_tal_lin.nii.gz', torchio.INTENSITY),
    Image('t2', '/tmp/colin27_t2_tal_lin.nii', torchio.INTENSITY),
    Image('label', '/tmp/colin27_seg1.nii.gz', torchio.LABEL),
]
subjects_list = [subject_a, subject_b]
subjects_dataset = torchio.ImagesDataset(subjects_list)
subject_sample = subjects_dataset[0]
```


#### [Samplers](torchio/sampler/sampler.py)

`torchio` includes grid, uniform and label patch samplers. There is also an
aggregator used for dense predictions.
For more information about patch-based training, see
[NiftyNet docs](https://niftynet.readthedocs.io/en/dev/window_sizes.html).

```python
import torch
import torchio

CHANNELS_DIMENSION = 1
patch_overlap = 4
grid_sampler = torchio.inference.GridSampler(
    input_array,  # some NumPy array
    patch_size=128,
    patch_overlap=patch_overlap,
)
patch_loader = torch.utils.data.DataLoader(grid_sampler, batch_size=4)
aggregator = torchio.inference.GridAggregator(
    input_array,
    patch_overlap=patch_overlap,
)

with torch.no_grad():
    for patches_batch in patch_loader:
        input_tensor = patches_batch['image']
        locations = patches_batch['location']
        logits = model(input_tensor)  # some torch.nn.Module
        labels = logits.argmax(dim=CHANNELS_DIMENSION, keepdim=True)
        outputs = labels
        aggregator.add_batch(outputs, locations)

output_array = aggregator.output_array
```


#### [`Queue`](torchio/queue.py)

A patches `Queue` (or buffer) can be used for randomized patch-based sampling
during training.
[This interactive animation](https://niftynet.readthedocs.io/en/dev/config_spec.html#queue-length)
can be used to understand how the queue works.

```python
import torch
import torchio

patches_queue = torchio.Queue(
    subjects_dataset=subjects_dataset,  # instance of torchio.ImagesDataset
    queue_length=300,
    samples_per_volume=10,
    patch_size=96,
    sampler_class=torchio.sampler.ImageSampler,
    num_workers=4,
    shuffle_subjects=True,
    shuffle_patches=True,
)
patches_loader = DataLoader(patches_queue, batch_size=4)

num_epochs = 20
for epoch_index in range(num_epochs):
    for patches_batch in patches_loader:
        logits = model(patches_batch)  # model is some torch.nn.Module
```


### Transforms

The transforms package should remind users of
[`torchvision.transforms`](https://pytorch.org/docs/stable/torchvision/transforms.html).
They take as input the samples generated by an [`ImagesDataset`](#dataset).

A transform can be quickly applied to an image file using the command-line
tool `torchio-transform`:

```shell
$ torchio-transform input.nii.gz RandomMotion output.nii.gz --kwargs "proportion_to_augment=1 num_transforms=4"
```

#### Augmentation

##### Intensity

###### [MRI k-space motion artifacts](torchio/transforms/augmentation/intensity/random_motion.py)

Magnetic resonance images suffer from motion artifacts when the subject moves
during image acquisition. This transform follows
[Shaw et al., 2019](http://proceedings.mlr.press/v102/shaw19a.html) to
simulate motion artifacts for data augmentation.

![MRI k-space motion artifacts](https://raw.githubusercontent.com/fepegar/torchio/master/images/random_motion.gif)


###### [MRI magnetic field inhomogeneity](torchio/transforms/augmentation/intensity/random_bias_field.py)

MRI magnetic field inhomogeneity creates slow frequency intensity variations.
This transform is very similar to the one in
[NiftyNet](https://niftynet.readthedocs.io/en/dev/niftynet.layer.rand_bias_field.html).

![MRI bias field artifacts](https://raw.githubusercontent.com/fepegar/torchio/master/images/random_bias_field.gif)


###### [Gaussian noise](torchio/transforms/augmentation/intensity/random_noise.py)

Adds noise sampled from a normal distribution with mean 0 and standard
deviation sampled from a uniform distribution in the range `std_range`.
It is often used after [`ZNormalization`](#z-normalization), as the output of
this transform has zero-mean.

![Random Gaussian noise](https://raw.githubusercontent.com/fepegar/torchio/master/images/random_noise.gif)


##### Spatial

###### [B-spline dense elastic deformation](torchio/transforms/augmentation/spatial/random_elastic_deformation.py)

![Random elastic deformation](https://raw.githubusercontent.com/fepegar/torchio/master/images/random_elastic_deformation.gif)


###### [Flip](torchio/transforms/augmentation/spatial/random_flip.py)

Reverse the order of elements in an image along the given axes.


###### [Affine transform](torchio/transforms/augmentation/spatial/random_affine.py)


#### Preprocessing

##### [Histogram standardization](torchio/transforms/preprocessing/histogram_standardization.py)

Implementation of
[*New variants of a method of MRI scale standardization*](https://ieeexplore.ieee.org/document/836373)
adapted from NiftyNet.

![Histogram standardization](https://raw.githubusercontent.com/fepegar/torchio/master/images/histogram_standardization.png)


##### [Z-normalization](torchio/transforms/preprocessing/z_normalization.py)

This transform first extracts the values with intensity greater than the mean,
which is an approximation of the foreground voxels.
Then the foreground mean is subtracted from the image and it is divided by the
foreground standard deviation.

![Z-normalization](https://raw.githubusercontent.com/fepegar/torchio/master/images/z_normalization.png)


##### [Rescale](torchio/transforms/preprocessing/rescale.py)

Rescale intensity values in an image to a certain range.


##### [Resample](torchio/transforms/preprocessing/resample.py)

Resample images to a new voxel spacing using `nibabel`.


##### [Pad](torchio/transforms/preprocessing/pad.py)

Pad images, like in [`torchvision.transforms.Pad`](https://pytorch.org/docs/stable/torchvision/transforms.html#torchvision.transforms.Pad).


##### [Crop](torchio/transforms/preprocessing/crop.py)

Crop images passing 1, 3, or 6 integers, as in [Pad](#pad).


## [Example](examples/example_times.py)

This example shows the improvement in performance when multiple workers are
used to load and preprocess the volumes using multiple workers.

```python
import time
import multiprocessing as mp

from tqdm import trange

import torch.nn as nn
from torch.utils.data import DataLoader
from torchvision.transforms import Compose

from torchio import ImagesDataset, Queue, DATA
from torchio.sampler import ImageSampler
from torchio.utils import create_dummy_dataset
from torchio.transforms import (
    ZNormalization,
    RandomNoise,
    RandomFlip,
    RandomAffine,
)


# Define training and patches sampling parameters
num_epochs = 4
patch_size = 128
queue_length = 400
samples_per_volume = 10
batch_size = 4

class Network(nn.Module):
    def __init__(self):
        super().__init__()
        self.conv = nn.Conv3d(
            in_channels=1,
            out_channels=3,
            kernel_size=3,
        )
    def forward(self, x):
        return self.conv(x)

model = Network()

# Create a dummy dataset in the temporary directory, for this example
subjects_list = create_dummy_dataset(
    num_images=100,
    size_range=(193, 229),
    force=False,
)

# Each element of subjects_list is a dictionary:
# subject_images = [
#     torchio.Image('one_image', path_to_one_image, torchio.INTENSITY),
#     torchio.Image('another_image', path_to_another_image, torchio.INTENSITY),
#     torchio.Image('a_label', path_to_a_label, torchio.LABEL),
# ]

# Define transforms for data normalization and augmentation
transforms = (
    ZNormalization(),
    RandomNoise(std_range=(0, 0.25)),
    RandomAffine(scales=(0.9, 1.1), degrees=10),
    RandomFlip(axes=(0,)),
)
transform = Compose(transforms)
subjects_dataset = ImagesDataset(subjects_list, transform)


# Run a benchmark for different numbers of workers
workers = range(mp.cpu_count() + 1)
for num_workers in workers:
    print('Number of workers:', num_workers)

    # Define the dataset as a queue of patches
    queue_dataset = Queue(
        subjects_dataset,
        queue_length,
        samples_per_volume,
        patch_size,
        ImageSampler,
        num_workers=num_workers,
    )
    batch_loader = DataLoader(queue_dataset, batch_size=batch_size)

    start = time.time()
    for epoch_index in trange(num_epochs, leave=False):
        for batch in batch_loader:
            # The keys of batch have been defined in create_dummy_dataset()
            inputs = batch['one_modality'][DATA]
            targets = batch['segmentation'][DATA]
            logits = model(inputs)
    print('Time:', int(time.time() - start), 'seconds')
    print()
```


Output:
```python
Number of workers: 0
Time: 394 seconds

Number of workers: 1
Time: 372 seconds

Number of workers: 2
Time: 278 seconds

Number of workers: 3
Time: 259 seconds

Number of workers: 4
Time: 242 seconds
```


## Related projects

* [Albumentations](https://github.com/albumentations-team/albumentations)
* [`batchgenerators`](https://github.com/MIC-DKFZ/batchgenerators)
* [kornia](https://kornia.github.io/)
* [DALI](https://developer.nvidia.com/DALI)
* [`rising`](https://github.com/PhoenixDL/rising)


## See also

* [`highresnet`](https://www.github.com/fepegar/highresnet)
* [`unet`](https://www.github.com/fepegar/unet)
