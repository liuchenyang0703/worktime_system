import pymysql

# config.py
DB_CONFIG = {
    'host': '172.16.10.65',
    'user': 'root',
    'password': '123123',
    'database': 'commute',
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}