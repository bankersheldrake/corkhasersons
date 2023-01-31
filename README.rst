=========================================================
Useful scripts for develpoer bankersheldrake
=========================================================

.. image:: https://travis-ci.org/jkoelker/python-nest.svg?branch=master
    :target: https://travis-ci.org/jkoelker/python-nest


Installation
============

.. code-block:: bash

    [sudo] pip install python-nest



Usage
=====

.. code-block:: python

    import nest

    napi = nest.Nest(client_id=client_id, client_secret=client_secret, access_token_cache_file=access_token_cache_file)
    while napi.update_event.wait():
        napi.update_event.clear()
        # assume you have one Nest Camera
        print (napi.structures[0].cameras[0].motion_detected)

If you use asyncio:
    You have to wrap ``update_event.wait()`` in an ``ThreadPoolExecutor``, for example:

.. code-block:: python

    import asyncio
    import nest

    napi = nest.Nest(client_id=client_id, client_secret=client_secret, access_token_cache_file=access_token_cache_file)
    event_loop = asyncio.get_event_loop()
    try:
        event_loop.run_until_complete(nest_update(event_loop, napi))
    finally:
        event_loop.close()

    async def nest_update(loop, napi):
        with ThreadPoolExecutor(max_workers=1) as executor:
            while True:
                await loop.run_in_executor(executor, nest.update_event.wait)
                nest.update_event.clear()
                # assume you have one Nest Camera
                print (napi.structures[0].cameras[0].motion_detected)


Module
------

You can import the module as ``nest``.

.. code-block:: python

    import nest
    import sys

    client_id = 'XXXXXXXXXXXXXXX'
    client_secret = 'XXXXXXXXXXXXXXX'
    access_token_cache_file = 'nest.json'



Command line
------------

.. code-block:: bash

    usage: exec [-h] [--conf FILE] [--token-cache TOKEN_CACHE_FILE] [-t TOKEN]
                [--client-id ID] [--client-secret SECRET] [-k] [-c] [-s SERIAL]
                [-S STRUCTURE] [-i INDEX] [-v]
                {temp,fan,mode,away,target,humid,target_hum,show,camera-show,camera-streaming,protect-show}
                ...


    positional arguments:
      {temp,fan,mode,away,target,humid,target_hum,show,camera-show,camera-streaming,protect-show}
                            command help
        temp                show/set temperature
        fan                 set fan "on" or "auto"
        mode                show/set current mode
        away                show/set current away status
        target              show current temp target
        humid               show current humidity
        target_hum          show/set target humidty
        show                show everything
        camera-show         show everything (for cameras)
        camera-streaming    show/set camera streaming
        protect-show        show everything (for Nest Protect)

    optional arguments:
      -h, --help            show this help message and exit
      --conf FILE           config file (default ~/.config/nest/config)
      --token-cache TOKEN_CACHE_FILE
                            auth access token cache file
      -t TOKEN, --token TOKEN
                            auth access token
      --client-id ID        product id on developer.nest.com
      --client-secret SECRET
                            product secret for nest.com
      -k, --keep-alive      keep showing update received from stream API in show
                            and camera-show commands
      -c, --celsius         use celsius instead of farenheit
      -s SERIAL, --serial SERIAL
                            optional, specify serial number of nest thermostat to
                            talk to
      -S STRUCTURE, --structure STRUCTURE
                            optional, specify structure name toscope device
                            actions
      -i INDEX, --index INDEX
                            optional, specify index number of nest to talk to
      -v, --verbose         showing verbose logging

    examples:
        # If your nest is not in range mode
        nest --conf myconfig --client-id CLIENTID --client-secret SECRET temp 73
        

A configuration file must be specified and used


.. code-block:: ini

    [SOMEINI]
    value=value



History
=======
 TBD