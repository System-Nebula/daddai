import logging

class Logger:
    def cfg(level):
        if level == 'debug':
            logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(message)s', datefmt='%y-%m-%d %H:%M:%S')
        else:
            print(f'only debug mode is available')
            exit(1)
    def writter(message):
        logging.debug(message)
