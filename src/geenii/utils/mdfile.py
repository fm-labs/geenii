import yaml
import os

class MarkdownFile:

    def __init__(self, file_path: str, parse: bool = True):
        """
        Read and parse the skill markdown file from the specified directory.

        :param file_path: The directory containing the SKILL.md file.
        :return: A tuple containing the skill header and body content.
        """
        self.file_path = file_path
        self.header = None
        self.body = None
        if parse:
            self.parse()

    def parse(self):
        file_path = self.file_path
        if not file_path or not os.path.isfile(file_path):
            raise ValueError(f"Skill markdown file not found: '{file_path}'")

        contents = ""
        with open(file_path, "r") as f:
            contents = f.read()

        if not contents.startswith("---"):
            raise ValueError("Malformed skill markdown file: missing header delimiter.")

        # find the second occurrence of '---' to determine the end of the header
        second_header_index = contents.find("---", 3)
        if second_header_index == -1:
            raise ValueError("Malformed skill markdown file: missing second header delimiter.")

        # extract the header and body sections
        header_str = contents[3:second_header_index].strip()
        self.body = contents[second_header_index + 3:].strip()

        # the header str is expected to be in YAML format, we can parse it into a dict
        try:
            header_dict = yaml.safe_load(header_str)
        except yaml.YAMLError as e:
            raise ValueError(f"Malformed skill markdown file: error parsing header YAML. {str(e)}")
        self.header = header_dict



def read_frontmatter_file(file_path: str) -> tuple[dict, str]:
    """
    Read and parse the markdown file from the specified directory.

    :param file_path: The directory containing the SKILL.md file.
    :return: A tuple containing the frontmatter header and body content.
    """
    if not file_path or not os.path.isfile(file_path):
        raise ValueError(f"File not found: '{file_path}'")

    contents = ""
    with open(file_path, "r") as f:
        contents = f.read()

    if not contents.startswith("---"):
        raise ValueError("Malformed frontmatter markdown file: missing header delimiter.")

    # find the second occurrence of '---' to determine the end of the header
    second_header_index = contents.find("---", 3)
    if second_header_index == -1:
        raise ValueError("Malformed frontmatter markdown file: missing second header delimiter.")

    # extract the header and body sections
    header = contents[3:second_header_index].strip()
    body = contents[second_header_index + 3:].strip()

    # the header str is expected to be in YAML format, we can parse it into a dict
    try:
        header_dict = yaml.safe_load(header)
    except yaml.YAMLError as e:
        raise ValueError(f"Malformed frontmatter markdown file: error parsing header YAML. {str(e)}")

    return header_dict, body