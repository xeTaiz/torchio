import numbers
from abc import abstractmethod

import torch
import SimpleITK as sitk

from .. import Transform


class RandomTransform(Transform):
    def __init__(self, seed=None, verbose=False):
        super().__init__(verbose=verbose)
        self.seed = seed

    def __call__(self, sample):
        self.check_seed()
        return super().__call__(sample)

    @staticmethod
    @abstractmethod
    def get_params():
        pass

    @staticmethod
    def nib_to_sitk(array, affine):
        """
        TODO: figure out how to get directions from affine
        so that I don't need this
        """
        import nibabel as nib
        from tempfile import NamedTemporaryFile
        if isinstance(array, torch.Tensor):
            array = array.numpy()
        with NamedTemporaryFile(suffix='.nii') as f:
            nib.Nifti1Image(array, affine).to_filename(f.name)
            image = sitk.ReadImage(f.name)
        return image

    @staticmethod
    def parse_range(nums_range, name):
        """Adapted from torchvision.RandomRotation"""
        if isinstance(nums_range, numbers.Number):
            if nums_range < 0:
                raise ValueError(
                    f'If {name} is a single number,'
                    f' it must be positive, not {nums_range}')
            return (-nums_range, nums_range)
        else:
            if len(nums_range) != 2:
                raise ValueError(
                    f'If {name} is a sequence,'
                    f' it must be of len 2, not {nums_range}')
            min_degree, max_degree = nums_range
            if min_degree > max_degree:
                raise ValueError(
                    f'If {name} is a sequence, the second value must be'
                    f' equal or greater than the first, not {nums_range}')
            return nums_range

    def parse_degrees(self, degrees):
        return self.parse_range(degrees, 'degrees')

    def parse_translation(self, translation):
        return self.parse_range(translation, 'translation')

    def check_seed(self):
        if self.seed is not None:
            torch.manual_seed(self.seed)
