import logging
from scripts.minecraft_resources import prepare_resources_references

logging.basicConfig(level=logging.INFO, format='[%(asctime)s %(levelname)s]: %(message)s')


if __name__ == '__main__':
    logging.info("Starting minecraft resource reference preparation")
    prepare_resources_references(["1.17.1", "24w38a", "1.21.1"])
    logging.info("Minecraft resource reference preparation completed")