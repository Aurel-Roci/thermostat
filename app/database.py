from influxdb import InfluxDBClient
import os

my_client = InfluxDBClient(os.getenv('HOST'),
                           os.getenv('PORT'),
                           os.getenv('USERNAME'),
                           os.getenv('PASSWORD'),
                           os.getenv('DB_NAME'))


class Database(object):

    def __init__(self):
        print('Get database client')
        try:
            self.client = my_client
            self.client.create_database(os.getenv('DB_NAME'))
            self.client.create_retention_policy('awesome_policy', '14d', '3', default=True)
        except Exception as ex:
            print("Error creating client: {0}".format(ex))

    def write(self, json_body):
        try:
            self.client.write_points(json_body, 's')
        except Exception as ex:
            print("Error writing data: {0}".format(ex))

    def query(self, query):
        print("Query: {0}".format(query))
        try:
            self.client.query(query)
        except Exception as ex:
            print("Error querying data: {0}".format(ex))

