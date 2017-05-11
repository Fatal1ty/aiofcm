import logging


logging.getLogger('aioxmpp').setLevel(logging.CRITICAL)
logging.getLogger('aioopenssl').setLevel(logging.CRITICAL)
logging.getLogger('aiosasl').setLevel(logging.CRITICAL)

logger = logging.getLogger('aiofcm')
