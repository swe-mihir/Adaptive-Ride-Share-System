"""
Database configuration file
Place this in the same directory as your server.py
"""
from configparser import ConfigParser


def config(filename='database/database.ini', section='postgresql'):
    """
    Read database configuration from ini file
    """
    # Create a parser
    parser = ConfigParser()

    # Read config file
    parser.read(filename)

    # Get section, default to postgresql
    db = {}
    if parser.has_section(section):
        params = parser.items(section)
        for param in params:
            db[param[0]] = param[1]
    else:
        raise Exception(f'Section {section} not found in the {filename} file')

    return db