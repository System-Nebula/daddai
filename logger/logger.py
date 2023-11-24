import logging
import os

class Logger:
    def cfg(file, level):
        if level == 'debug':
            logging.basicConfig(filename=file, level=logging.DEBUG, format='%(asctime)s - %(message)s', datefmt='%y-%m-%d %H:%M:%S')
        else:
            print(f'only debug mode is available')
            os.Exit(1) 
    def writter(message):
        logging.debug(message)
