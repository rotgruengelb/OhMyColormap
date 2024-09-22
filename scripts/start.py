import logging
from scripts.gen_reference import prepare_resources_references
from scripts.init_assemble import initialize_assembly

logging.basicConfig(level=logging.INFO, format='[%(asctime)s %(levelname)s]: %(message)s')

BUILD_REFERENCE_DIR = "../build/reference"
BUILD_ASSEMBLE_DIR = "../build/assemble"


def build():
    logging.info("Starting minecraft resource reference preparation")
    prepare_resources_references(["1.17.1", "24w38a", "1.21.1"])
    logging.info("Minecraft resource reference preparation completed")
    initialize_assembly()
