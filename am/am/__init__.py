"""Account Manager."""

# PyMySQL stands in for MySQLdb, Django's MySQL and MariaDB driver, as in smarter-sh/smarter.
import pymysql

from .__version__ import __version__ as _version

pymysql.install_as_MySQLdb()


__title__ = "Account Manager"
__description__ = "A platform for managing user accounts and payments."
__version__ = _version
__author__ = "Lawrence McDaniel"
__author_email__ = "lpm0073@gmail.com"
__copyright__ = "Copyright (c) 2025 Lawrence McDaniel"
__url__ = "https://github.com/smarter-sh/smarter-account"
