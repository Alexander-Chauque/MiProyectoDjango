import pymysql
pymysql.install_as_MySQLdb()

# TRUCO PARA REEMPLAZAR 'cgi' (Que Python 3.13 eliminó)
import sys, types
