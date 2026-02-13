import os
import shutil
import random

def random_sample_files(input_folder, output_folder, sample_size):
    """
    Randomly sample a specified number of files from the input folder
    """

    # Create output folder if it doesn't exist
    os.makedirs(output_folder, exist_ok=True)

    # Get a list of all files in the input folder
    all_files = [f for f in os.listdir(input_folder) if os.path.isfile(os.path.join(input_folder, f))]

    # Check that sample_size is not larger than the number of available files
    if sample_size > len(all_files):
        raise ValueError(f"Requested {sample_size} files, but only {len(all_files)} available.")

    # Randomly select the specified number of files
    sampled_files = random.sample(all_files, sample_size)

    # Copy the selected files to the destination folder
    for f in sampled_files:
        input_path = os.path.join(input_folder, f)
        output_path = os.path.join(output_folder, f)
        shutil.copy2(input_path, output_path)

    print(f"Copied {len(sampled_files)} files from {input_folder} to {output_folder}")

# Paths relative to the project root
src_folder = "crops/IMG_2871 2026_02_05 no possum 652"
dst_folder = "crops/choice/train/not_possums/IMG_2871 2026_02_05 no possum 150"

# Turn relative paths into absolute paths based on current working directory
src_folder_full = os.path.join(os.getcwd(), src_folder)
dst_folder_full = os.path.join(os.getcwd(), dst_folder)

sample_count = 150

random_sample_files(src_folder_full, dst_folder_full, sample_count)
