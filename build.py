import logging
from scripts.minecraft_resources import prepare_minecraft_resources

logging.basicConfig(level=logging.INFO, format='[%(asctime)s %(levelname)s]: %(message)s')


if __name__ == '__main__':
    logging.info("Starting resource preparation")
    prepare_minecraft_resources(["1.17.1", "24w38a", "1.21.1"])
    logging.info("Resource preparation completed")