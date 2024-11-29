from skimage import io
from skimage.metrics import structural_similarity as ssim
from pathlib import Path


class ImageComparator:
    """
    This class simply uses skimage to compare two images.
    There is a method to compute the 'similarity' as a float [0; 1]
    and the method 'changed' to return a boolean, when the images are different.
    """
    @staticmethod
    def similarity(img1_filename: Path, img2_filename: Path) -> int:
        image1 = io.imread(img1_filename, as_gray=True)
        image2 = io.imread(img2_filename, as_gray=True)
        s = ssim(image1, image2, data_range=image1.max() - image1.min())
        return s

    def changed(self, img1_filename: Path, img2_filename: Path, sim_threshold=0.9):
        return self.similarity(img1_filename, img2_filename) < sim_threshold


if __name__ == '__main__':

    img1 = Path('/Users/joba/Desktop/CG_TestImages/20240614_125608.jpeg')
    img2 = Path('/Users/joba/Desktop/CG_TestImages/20240614_151132.jpeg')

    app = ImageComparator()
    similarity = app.similarity(img1, img2)
    changed = app.changed(img1, img2)
    print(f"Similarty: {similarity} / Changed: {changed}")
