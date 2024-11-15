import configparser

from treelib import Tree
import re
from subprocess import check_output, Popen, PIPE, CalledProcessError
import tqdm
from sys import stderr
from platform import system
import traceback


class File:
    def __init__(self, full_path, size, last_modified, attribute):
        self.fullPath = full_path.rstrip("/")
        self.size = size if type(size) is int else int(size.replace(".", ""))
        self.lastModified = last_modified
        self.attribute = attribute
        if full_path[-1] != "/":  # not a folder
            self.name = full_path.split("/")[-1]
        else:
            self.name = full_path.split("/")[-2]

    def __str__(self):
        return f"{self.lastModified}\t{self.size:>14} {self.attribute:10}\t {self.fullPath}"

    def is_directory(self):
        return "D" in self.attribute


def build_parent_nodes(tree: Tree, path: str):
    parent_path = '/'.join(path.split('/')[0:-1])

    # TODO: verify works with non-windows drive root dir/linux directories
    if parent_path.find('/') == -1:
        if not tree.get_node(parent_path):  # parent is root
            data = File(parent_path, 0, 0, "D")
            tree.create_node(parent_path, parent_path, data=data)
        return parent_path
    elif not tree.get_node(parent_path):
        build_parent_nodes(tree, parent_path)
        data = File(parent_path, 0, 0, "D")
        tree.create_node(parent_path, parent_path, parent=build_parent_nodes(tree, parent_path), data=data)

    return parent_path


def add_node_new(tree: Tree, node: File):
    build_parent_nodes(tree, node.fullPath)
    if tree.get_node(node.fullPath):
        tree.get_node(node.fullPath).data = node
        return

    parent_path = node.fullPath[0:-(len(node.name) + 1)]
    tree.create_node(node.fullPath, node.fullPath, parent=parent_path, data=node)
    return


def create_filetree(tree: Tree, contents):
    pattern = re.compile(
        r"-\s(?P<daytime>[0-9]{4}-[0-9]{2}-[0-9]{2}\s[0-9]{2}:[0-9]{2}:[0-9]{2})\s+"
        r"(?P<size>[0-9]+(\.[0-9]+)*)\s+(?P<attribute>[A-Za-z0-9]+)\s+(?P<path>.*)")
    num_files_pattern = re.compile(r"([0-9]+(\.[0-9])*)+\sfiles")

    # Find number of files for estimate (this appears to be off because of the versions?)
    num_files = 1000
    # for line in contents:
    #     num_files -= 1
    #     match = re.search(num_files_pattern, line)
    #     if match:
    #         temp = match.group()
    #         num_files = int(temp[0:temp.find(" files")].replace(".", ""))
    #         break
    #     elif line.find("ERROR_FILE_NOT_FOUND") != -1:
    #         print("ZPAQ file not found.", file=stderr)
    #         exit(1)
    #     elif line.find("Usage") != -1:
    #         print("ZPAQ path may have been entered improperly.", file=stderr)
    #         exit(1)

    print("Creating file tree...")
    bar = tqdm.tqdm(contents, total=num_files, unit="files", colour="green", leave=False)
    for line in bar:
        try:
            if "," in line and "-csv" not in line:
                line = line.rstrip()
                #date, _, __, attribute, fullpath = re.search(pattern, line).groups()
                #size = re.search(pattern, line).group("size")
                datetime, attribute, size, ratio, _, fullpath = line.split(",")
                date = datetime.split(" ")[0]

                date = date.strip("'")
                attribute = attribute.strip("'")
                size = size.strip("'")
                ratio = ratio.strip("'")
                fullpath = fullpath.strip("'")

                testfile = File(fullpath, size, date, attribute)
                add_node_new(tree, testfile)
            else:
                # num_files -= 1
                # bar.total = num_files
                # bar.refresh()
                pass
        except IndexError:  # sometimes line[0] is invalid
            pass

    # Ideally would update bar total here instead of just closing and hiding it with leave=False
    bar.close()


def extract_file(config, zpaq_file, extract_from_path, extract_to_path, is_directory=False):
    if is_directory: #len(tree.children(node)) != 0:  # assumes all folders have 0 children
        # must include trailing /
        if extract_to_path[-1] != "/":
            extract_to_path += "/"
        if extract_from_path[-1] != "/":
            extract_from_path += "/"

        if system() == "Windows":
            command = [config.get('config', 'zpaq_path'), "x", zpaq_file, extract_from_path, "-to", extract_to_path, "-longpath",
                       "-find", extract_from_path]
        else:
            command = [config.get('config', 'zpaq_path'), "x", zpaq_file, extract_from_path, "-to", extract_to_path]
    else:  # is file or empty directory
        if system() == "Windows":
            if extract_to_path[-1] == "/":  # must drop trailing /
                extract_to_path = extract_to_path[:-1]
            command = [config.get('config', 'zpaq_path'), "x", zpaq_file, extract_from_path, "-to", extract_to_path, "-longpath",
                       "-find", '/'.join(extract_from_path.split('/')[:-1]) + "/"]
            if extract_to_path[-1] == ":":  # when extracting to directory root, -space is required for some reason
                command.append("-space")
        else:
            # must include trailing /
            if extract_from_path[-1] == "/":
                extract_to_path += extract_from_path.split("/")[-2]
            else:
                extract_to_path += extract_from_path.split("/")[-1]
            command = [config.get('config', 'zpaq_path'), "x", zpaq_file, extract_from_path, "-to", extract_to_path]

    print(f"Command: {command}")
    try:
        print(check_output(command).decode("utf-8"))
    except Exception as e:  # CalledProcessError as e:
        print(f"Something went wrong with extracting. Error: {traceback.format_exc()}")

    return extract_to_path + "/" + extract_from_path.split("/")[-1]


def read_file(config, zpaq_file, extract_from_path):
    try:
        command = [config.get('config', 'zpaq_path'), "x", zpaq_file, extract_from_path, "-longpath", "-stdout"]
        print(f"Command: {command}")
        return check_output(command)
    except Exception as e:  # CalledProcessError as e:
        print(f"Something went wrong with extracting. Error: {traceback.format_exc()}")



def explore_tree(tree: Tree, config, zpaq_file: str = None):
    user_input = "0"
    curr_node = tree.root
    while user_input != 'q' and user_input != 'Q':
        print(f"Current node: {curr_node}")
        if not tree.get_node(curr_node).data.is_directory():
            print("Is file.")
            print("Enter .. to go back a directory. Enter root to go back to "
                  "root.\nEnter s to save tree to file.\nEnter x to extract file/directory.\nEnter q to quit")
        elif len(tree.children(curr_node)) == 0:
            print("Directory empty.")
            print("Enter .. to go back a directory. Enter root to go back to "
                  "root.\nEnter s to save tree to file.\nEnter x to extract file/directory.\nEnter q to quit")
        else:
            for index, node in enumerate(tree.children(curr_node)):
                print(f"{index + 1:>4}: {node.data}")
            print("Enter a node number to explore it.\nEnter .. to go back a directory. Enter root to go back to "
                  "root.\nEnter s to save tree to file.\nEnter x to extract file/directory.\nEnter q to quit")

        user_input = input()
        if user_input == 'q' or user_input == 'Q':
            break
        elif user_input == 's':
            file_type = input("Enter text or json: ")
            path = input("Enter path: ")
            try:
                if file_type == "text":
                    tree.save2file(path)
                elif file_type == "json":
                    open(path, 'w').write(tree.to_json())
                else:
                    print("Invalid file type selected.")
            except Exception as e:  # FileNotFoundError, OSError Invalid argument,
                print(f"Something went wrong with the file path. Error: {traceback.format_exc()}", file=stderr)
            continue
        elif user_input.isnumeric() and 0 < int(user_input) <= len(tree.children(curr_node)):
            curr_node = tree.children(curr_node)[int(user_input) - 1].identifier
            continue
        elif user_input == '..':
            if tree.parent(curr_node) is not None:
                curr_node = tree.parent(curr_node).identifier
            else:
                print("Already at root.")
            continue
        elif user_input == 'root':
            curr_node = tree.root
            continue
        elif user_input == 'x':
            if zpaq_file is None:
                zpaq_file = input("Please specify path to zpaq file: ")
            extract_path = input("Enter extract path (not including file/directory name): ").replace("\\", "/")
            node = tree.get_node(curr_node)
            extract_file(config, zpaq_file, node.data.fullPath, extract_path, not node.is_leaf())
        else:
            print("Invalid input. Please try again.")
            continue


def load_create_config():
    config = configparser.ConfigParser()
    config.read('config.ini')
    needToWrite = False
    if not config.has_section('config'):
        config.add_section('config')
        needToWrite = True
    if not config.has_option('config', 'zpaq_path'):
        try:
            check_output(["zpaqfranz"])
            config.set('config', 'zpaq_path', 'zpaqfranz')
            print("zpaqfranz found.")
        except CalledProcessError:
            zpaq_path = input("Enter zpaqfranz path (no quotes): ")
            # retry until valid
            valid_path = False
            while not valid_path:
                try:
                    check_output([zpaq_path])
                    valid_path = True
                except CalledProcessError:
                    zpaq_path = input("Path was invalid, please try again. Enter zpaqfranz path (no quotes): ")
            config.set('config', 'zpaq_path', zpaq_path)
        needToWrite = True
    if config.has_option('config', 'zpaq_path'):
        valid_path = False
        while not valid_path:
            try:
                check_output([config.get('config', 'zpaq_path')])
                valid_path = True
                needToWrite = True
            except Exception as e:
                print(f"Something went wrong with zpaqfranz.\nError: {e.with_traceback()}", file=stderr)
                zpaq_path = input("Path was invalid, please try again. Enter zpaqfranz path (no quotes): ")
                config.set('config', 'zpaq_path', zpaq_path)
    if needToWrite:
        with open('config.ini', 'w') as configfile:
            config.write(configfile)
    return config


def linux_tests():
    # zpaqfranz x "/mnt/b/g_drive.zpaq" "G:/.minecraft/screenshots/2019-05-09_21.57.51.png" -to "/mnt/b/tempout/2019-05-09_21.57.51.png"
    print(check_output(["zpaqfranz", "x", "/mnt/b/g_drive.zpaq", "G:/.minecraft/screenshots/2019-05-09_21.57.51.png", "-to", "/mnt/b/tempout/2019-05-09_21.57.51.png"]).decode("utf-8"))


def main(config=None, file_path=None):
    if config is None:
        config = load_create_config()
    if file_path is None:
        file_path = input("Enter file path to load: ")

    ext = file_path.split('.')[-1]
    zpaqpath = config.get('config', 'zpaq_path')
    zpaq_file = None
    try:
        if ext == 'zpaq':
            contents = Popen([zpaqpath, "l", file_path, "-longpath", "-terse", "-csv", "','"], stdout=PIPE, encoding="utf-8",
                             errors="ignore").stdout
            zpaq_file = file_path
        elif ext == 'txt':
            contents = open(file_path, 'r', encoding="utf-8")
        else:
            print("Invalid file type.", file=stderr)
            exit(1)
    except Exception as e:
        print(f"Something went wrong getting the file list. Error: {traceback.format_exc()}", file=stderr)
        exit(1)

    tree = Tree()
    try:
        create_filetree(tree, contents)
    except Exception as e:
        print(f"Something went wrong creating the file tree. Error: {traceback.format_exc()}", file=stderr)
        if ext == 'txt':
            contents.close()
        exit(1)

    if ext == 'txt':
        contents.close()

    if __name__ == "__main__":
        try:
            explore_tree(tree, config, zpaq_file)
        except Exception as e:
            print(f"Something went wrong exploring the file tree. Error: {traceback.format_exc()}", file=stderr)
            exit(1)
    else:
        return tree


if __name__ == "__main__":
    main()
