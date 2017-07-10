import os
import shutil


def copy_diffs(output_dir = "int_diffs"):
    os.makedirs(output_dir, exist_ok=True)
    with open("interesting_diffs.txt") as fs:
        for fn in fs:
            fn = fn[:len(fn)-1]
            dest_name = os.path.split(fn)[-1]
            dest_file = os.path.join(output_dir, dest_name)
            if os.path.exists(dest_file):
                dest_file += "_0"

            shutil.copy2(fn, dest_file)

if __name__ == '__main__':
    copy_diffs()
