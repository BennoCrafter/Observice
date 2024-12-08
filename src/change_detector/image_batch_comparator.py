import os
from PIL import Image, ImageFont, ImageDraw

from src.change_detector.image_comparator import ImageComparator


class ImageBatchComparator:
    """
    This class reads all jpeg images in a given directory and compares them with each other,
    generates a new image for each compared two images and write these to a new directory.
    In the image the similarity and the changed flag is also written.
    """
    def __init__(self):
        self.text_position = (20, 5)
        self.text_color = 'rgb(255, 255, 255)'  # White
        self.text_font = ImageFont.load_default()

        circle_center_x, circle_center_y = 10, 10
        circle_radius = 5
        left_up_point = (circle_center_x - circle_radius, circle_center_y - circle_radius)
        right_down_point = (circle_center_x + circle_radius, circle_center_y + circle_radius)
        self.circle_bbox = [left_up_point, right_down_point]

    @staticmethod
    def all_files(directory, file_suffix='jpeg'):
        collected = []
        for entry in os.listdir(directory):
            full_path = os.path.join(directory, entry)
            if os.path.isfile(full_path) and entry.endswith(file_suffix):
                collected.append(full_path)
        return collected

    def join_images(self, image1_filepath, image2_filepath, outfilepath, text=None, changed=None):
        img1 = Image.open(image1_filepath)
        img2 = Image.open(image2_filepath)

        img1_height = img1.size[1]
        img2_height = img2.size[1]
        if img1_height != img2_height:
            img2 = img2.resize((int(img2.size[0] * img1_height / img2_height), img1_height))

        # Create a new image with a width that is the sum of both images' widths
        total_width = img1.size[0] + img2.size[0]
        new_image = Image.new('RGB', (total_width, img1_height))

        # Paste the images into the new image
        new_image.paste(img1, (0, 0))
        new_image.paste(img2, (img1.size[0], 0))
        if text:
            self.draw_text(text, new_image)
        if changed is not None:
            self.draw_circle(changed, new_image)
        # Save the new image
        new_image.save(outfilepath)

    def draw_text(self, text, image):
        draw = ImageDraw.Draw(image)
        draw.text(self.text_position, text, fill=self.text_color, font=self.text_font)

    def draw_circle(self, changed, image):
        draw = ImageDraw.Draw(image)
        color = 'red'
        if changed:
            color = 'green'
        draw.ellipse(self.circle_bbox, fill=color, outline=color)

    @staticmethod
    def clean_dir(directory):
        for filename in os.listdir(directory):
            file_path = os.path.join(directory, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)  # Removes files and links
            except Exception as e:
                print(f'Failed to delete {file_path}. Reason: {e}')


if __name__ == '__main__':
    work_dir = '/Users/joba/Desktop/CG_TestImages/'
    generated_images_out_dir = '/Users/joba/Desktop/CG_TestImages/batchAnalysis/'

    app = ImageBatchComparator()
    app.clean_dir(generated_images_out_dir)
    comparator = ImageComparator()
    files = app.all_files(work_dir)
    for i in range(len(files)):
        for j in range(i+1, len(files)):
            out_filepath = generated_images_out_dir + 'analysis_' + str(i) + 'x' + str(j) + '.jpeg'

            sim = comparator.similarity(files[i], files[j])
            changed_image = comparator.changed(files[i], files[j])
            sim_text = format(sim, ".2f")
            app.join_images(files[i], files[j], out_filepath, text=sim_text, changed=changed_image)
