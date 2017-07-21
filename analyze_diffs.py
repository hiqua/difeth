"""
Analyze diffs produced by the crawler.
"""
import os
import shutil
from contextlib import suppress

from colorama import Fore, Style


def reset_style():
    """Reset colors
    """
    print(Style.RESET_ALL, end='')


def is_diff(diff_fn):
    """Tells if the file a diff, or full code.
    """
    return not diff_fn.endswith("_code")


def find_diffs(min_size, max_size, folder="diffs"):
    """Return diff with size in the interval

    Sizes are given in bytes.
    """
    for curr_dir, _, fns in os.walk(folder):
        for diff_fn in filter(is_diff, fns):
            full_path = os.path.join(curr_dir, diff_fn)
            size = os.path.getsize(full_path)
            if min_size <= size < max_size:
                yield (full_path, size)


def get_color(line):
    """Returns the color to add to this line.
    """
    color = ''
    if line == '---' or line == '+++':
        color = Fore.GREEN
    elif line.startswith('+'):
        color = Fore.CYAN
    elif line.startswith('-'):
        color = Fore.MAGENTA
    elif line.startswith('@@') and line.endswith('@@'):
        color = Fore.YELLOW

    return color


def print_diff(diff_fn):
    """Print the given diff with some syntax highlighting.
    """
    with open(diff_fn) as diff_fs:
        for line in diff_fs:
            # remove trailing \n
            line = line[:len(line) - 1]
            color = get_color(line)
            print(color + line)
            reset_style()


def unzip(lst):
    """unzip([(1,2),(3,4),(5,6)]) == [(1, 3, 5), (2, 4, 6)]
    """
    return list(zip(*lst))


def display_batch(min_size, max_size):
    """Display interactively the diffs of size in [min_size, max_size)
    """
    tmp = unzip(sorted(find_diffs(min_size, max_size), key=lambda a: a[1]))
    assert len(tmp) == 2
    diff_fns, sizes = tmp[0], tmp[1]

    i = 0
    while True:
        print(Fore.RED + "{}/{}: {} (size: {}B)"
              .format(i,
                      len(diff_fns),
                      diff_fns[i],
                      sizes[i]))

        reset_style()
        print_diff(diff_fns[i])
        if i == len(diff_fns) - 1:
            print("This is the last diff.")
        action = input("(s)ave diff, (p)revious, (n)ext (Enter), (q)uit\n")

        if action == "s":
            action = "n"
            yield diff_fns[i]

        if action == "n" or action == "":
            i = min(len(diff_fns) - 1, i + 1)
        elif action == "p":
            i = max(0, i-1)
        elif action == "q":
            break


def copy_diffs(saved_diff_fn, output_dir="interesting_diffs"):
    """Copy the diffs whose filenames are listed in the output_dir
    """
    os.makedirs(output_dir, exist_ok=True)
    with open(saved_diff_fn) as saved_diff_fs:
        for diff_fn in saved_diff_fs:
            diff_fn = diff_fn[:len(diff_fn)-1]
            dest_name = os.path.split(diff_fn)[-1]
            dest_file = os.path.join(output_dir, dest_name)
            if os.path.exists(dest_file):
                dest_file += "_0"

            shutil.copy2(diff_fn, dest_file)


if __name__ == '__main__':
    MIN_SIZE = 0000
    STEP = 10000
    SAVED_DIFF_FN = "interesting_diffs.txt"

    with suppress(FileNotFoundError):
        # loop / IO in this order to get the results right away
        for diff_fn_ in display_batch(MIN_SIZE, MIN_SIZE + STEP):
            with open(SAVED_DIFF_FN, 'a') as saved_diff_fs_:
                saved_diff_fs_.write(diff_fn_ + '\n')

        copy_diffs(saved_diff_fn=SAVED_DIFF_FN)
