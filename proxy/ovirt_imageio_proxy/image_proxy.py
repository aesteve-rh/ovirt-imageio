
import logging
import signal
import time

from M2Crypto import threading

# M2Crypto.threading needs initialization.
# See
# - https://bugzilla.redhat.com/482420
# - https://bugzilla.redhat.com/1576500
threading.init()

import systemd.daemon

import server


running = True
restart = False


def main(args, config):
    signal.signal(signal.SIGINT, terminate)
    signal.signal(signal.SIGTERM, terminate)
    signal.signal(signal.SIGHUP, reload_config)
    image_server = server.Server()
    image_server.start(config)

    # Now that the socket is listening, let systemd know we're ready
    ret = systemd.daemon.notify('READY=1')
    s = 'successfully notified' if ret else 'unable to notify'
    logging.info("Server started, %s systemd", s)

    try:
        while running:
            time.sleep(config.poll_interval)
    finally:
        image_server.stop()
    # TODO meaningful return value from above?
    # TODO if we fail, sd_notify("STATUS=Failed to start: {}")
    logging.info("Server shut down, exiting")
    return 0


def terminate(signo, frame):
    global running
    running = False


def reload_config(signo, frame):
    # TODO reconfigure service based on new config
    global restart
    restart = False
    pass
