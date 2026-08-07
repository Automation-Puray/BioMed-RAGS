# devices/experiment_setup.py
import asyncio
import logging
from .server_api_client import ServerAPIClient

async def get_experiment_duration_params(loop):
    """
    Asks the user for total duration and interval in minutes.
    Returns: (total_duration_min, interval_min, num_cycles)
    """
    print("\n--- Experiment Timing Configuration ---")
    while True:
        try:
            d_raw = await loop.run_in_executor(None, lambda: input("Enter Total Duration (minutes): ").strip())
            total_duration = float(d_raw)
            
            i_raw = await loop.run_in_executor(None, lambda: input("Enter Measurement Interval (minutes): ").strip())
            interval = float(i_raw)

            if interval <= 0 or total_duration <= 0:
                print("Duration and Interval must be positive numbers.")
                continue
            if interval > total_duration:
                print("Interval cannot be larger than Total Duration.")
                continue

            # Calculate number of cycles (Cycle 0 at start, then every interval)
            # If Duration=60, Interval=60 -> Cycle 0 (0m), Cycle 1 (60m) -> 2 Cycles.
            num_cycles = int(total_duration // interval) + 1
            
            print(f"-> Configuration Accepted: Approx {num_cycles} Cycles expected.")
            return total_duration, interval, num_cycles
        except ValueError:
            print("Invalid input. Please enter numeric values.")

async def select_or_create_fiber(api, loop):
    fibers = await loop.run_in_executor(None, api.get_fibers)
    id_map = {}
    code_map = {}
    for f in fibers:
        fid = int(f['fiber_id'])
        fcode = f.get('fiber_code') 
        id_map[fid] = f
        if fcode:
            code_map[str(fcode)] = f

    if not fibers:
        print("\nNo fibers found. Please register a new fiber.")
    else:
        print("\nAvailable Fibers:")
        for f in fibers:
            print(f"  ID: {f['fiber_code']} | Name: {f['fiber_name']}")

    while True:
        choice = await loop.run_in_executor(None, lambda: input("Enter a Fiber ID or Fiber Code (e.g. fiber_0001), or type 'new': ").strip())
        if choice.lower() == 'new':
            while True:
                fiber_name = await loop.run_in_executor(None, lambda: input("Fiber Name: ").strip())
                if fiber_name:
                    break
                logging.error("Fiber name cannot be empty. Please enter a valid name.")

            manufacturer = await loop.run_in_executor(None, lambda: input("Manufacturer: ").strip())
            
            while True:
                length = await loop.run_in_executor(None, lambda: input("Length (mm): ").strip())
                if not length:
                    length_val = None
                    break
                try:
                    length_val = float(length)
                    break
                except ValueError:
                    logging.error("Invalid input. Please enter a number for length.")
            
            while True:
                core_diameter = await loop.run_in_executor(None, lambda: input("Core Diameter (um): ").strip())
                if not core_diameter:
                    core_diameter_val = None
                    break
                try:
                    core_diameter_val = float(core_diameter)
                    break
                except ValueError:
                    logging.error("Invalid input. Please enter a number for core diameter.")
            coatings = await loop.run_in_executor(None, lambda: input("Coatings: ").strip())
            material = await loop.run_in_executor(None, lambda: input("Material: ").strip())
            connectorization = await loop.run_in_executor(None, lambda: input("Connectorization: ").strip())
            remarks = await loop.run_in_executor(None, lambda: input("Remarks: ").strip())

            result = await loop.run_in_executor(
                None,
                lambda: api.register_fiber(
                    fiber_name=fiber_name,
                    manufacturer=manufacturer,
                    length_mm=length_val,
                    core_diameter_um=core_diameter_val,
                    coatings=coatings,
                    material=material,
                    connectorization=connectorization,
                    remarks=remarks
                )
            )
            if result and 'error' in result:
                logging.error(f"Server Error: {result['error']}")
            elif result and 'fiber_id' in result:
                logging.info(f"New fiber registered with ID: {result['fiber_id']} and Code: {result.get('fiber_code')}")
                return int(result['fiber_id']), result['fiber_code']
            else:
                logging.error("Failed to register new fiber.")
                return None,None
        else:
            if choice in code_map:
                sel = code_map[choice]
                fid = int(sel['fiber_id'])
                logging.info(f"Selected existing Fiber Code: {sel['fiber_code']}")
                return fid, sel['fiber_code']
            try:
                fid = int(choice)
                if fid in id_map:
                    sel = id_map[fid]
                    logging.info(f"Selected existing Fiber Code:{sel['fiber_code']} (ID: {fid})")
                    return fid, sel['fiber_code']
                else:
                    logging.error("Invalid Fiber ID/Code. Please select a valid ID from the list.")
            except ValueError:
                logging.error("Invalid input. Enter numeric ID, fiber code (fiber_0001), or 'new'.")


async def select_or_create_catheter(api, loop):
    catheters = await loop.run_in_executor(None, api.get_catheters)
    id_map = {}
    code_map = {}
    for c in catheters:
        cid = int(c['cath_id'])
        code = c.get('cath_code')
        id_map[cid] = c
        if code:
            code_map[str(code)] = c

    if not catheters:
        print("\nNo catheters found. Please register a new catheter.")
    else:
        print("\nAvailable Catheters:")
        for c in catheters:
            print(f"  ID: {c['cath_code']} | Name: {c.get('cath_name','-')} | Material: {c.get('material','-')}")

    while True:
        choice = await loop.run_in_executor(None, lambda: input("Enter a Catheter Catheter Code (e.g. C0001), or type 'new': ").strip())
        if choice.lower() == 'new':
            while True:
                cath_name = await loop.run_in_executor(None, lambda: input("Catheter Name: ").strip())
                if cath_name:
                    break
                logging.error("Catheter name cannot be empty. Please enter a valid name.")
            model = await loop.run_in_executor(None, lambda: input("Model: ").strip())
            manufacturer = await loop.run_in_executor(None, lambda: input("Manufacturer: ").strip())
            material = await loop.run_in_executor(None, lambda: input("Material : ").strip())
            remarks = await loop.run_in_executor(None, lambda: input("Remarks : ").strip())

            result = await loop.run_in_executor(
                None,
                lambda: api.register_catheter(
                    cath_name=cath_name,
                    model=model,
                    manufacturer=manufacturer,
                    material=material,
                    remarks=remarks
                )
            )
            if result and 'error' in result:
                logging.error(f"Server Error: {result['error']}")
            elif result and 'cath_id' in result and 'cath_code' in result:
                logging.info(f"New catheter registered with ID: {result['cath_id']} and Code: {result.get('cath_code')}") 
                return int(result['cath_id']), result['cath_code'] 
            else:
                logging.error("Failed to register new catheter.")
                return None, None
        else:
            if choice in code_map:
                sel = code_map[choice]
                cid = int(sel['cath_id'])
                logging.info(f"Selected existing Catheter Code: {choice} (ID: {cid})")
                return cid, sel['cath_code']
            try:
                cid = int(choice)
                if cid in id_map:
                    sel = id_map[cid]
                    logging.info(f"Selected existing Catheter ID: {cid}")
                    return cid, sel['cath_code']
                else:
                    logging.error("Invalid Catheter ID. Please select a valid ID from the list.")
            except ValueError:
                logging.error("Invalid input. Enter cath code (C0001), or 'new'.")


async def setup_experiment(category="single"):
    """
    Setup experiment details.
    category: 'single' or 'long_term'
    """
    api = ServerAPIClient()
    loop = asyncio.get_running_loop()

    laser_source = ""
    while True:
        laser_prompt = (
            "\nLaser Source:\n"
            "  Press 1: BWT Bench Top\n"
            "  Press 2: Puray Prototype\n"
            "  Press 3: Osram Prototype\n"
            "Enter choice (1, 2, or 3): "
        )
        raw_laser = await loop.run_in_executor(None, lambda: input(laser_prompt).strip())
        
        if raw_laser == '1':
            laser_source = "BWT Bench Top"
            break
        elif raw_laser == '2':
            laser_source = "Puray Prototype"
            break
        elif raw_laser == '3':
            laser_source = "Osram Prototype"
            break
        else:
            logging.error("Invalid choice. Please enter 1, 2, or 3.")
    
    logging.info(f"Laser Source selected: {laser_source}")

    while True:
        exp_type = await loop.run_in_executor(
            None, lambda: input("\nEnter experiment type (fiber or cath): ").strip().lower()
        )

        if exp_type == "fiber":
            fiber_id, fiber_code  = await select_or_create_fiber(api, loop)
            if not fiber_id:
                return None, None, None, None, None, None, None 

            exp_id, fiber_exp_id, exp_code = await loop.run_in_executor(
                None, lambda: api.register_experiment(fiber_id=fiber_id, laser_source=laser_source, category=category)
            )

            if exp_id: 
                logging.info(f"Fiber Experiment registered: Experiment Code- {exp_code}")
                return fiber_id, None, exp_id, fiber_code, exp_code, None, laser_source
            else:
                logging.error("Failed to register fiber experiment.")
                return None, None, None, None, None, None, None

        elif exp_type == "cath":
            fiber_id, fiber_code = await select_or_create_fiber(api, loop)
            if not fiber_id:
                return None, None, None, None, None, None, None

            cath_id, cath_code = await select_or_create_catheter(api, loop)
            if not cath_id:
                return None, None, None, None, None, None, None

            exp_id, fiber_exp_id, exp_code = await loop.run_in_executor(
                None, lambda: api.register_experiment(fiber_id=fiber_id, cath_id=cath_id, laser_source=laser_source, category=category)
            )

            if exp_id: 
                logging.info(f"Catheter Experiment registered: Exp ID - {exp_code}")
                return fiber_id, cath_id, exp_id, fiber_code, exp_code, cath_code, laser_source
            else:
                logging.error("Failed to register catheter experiment.")
                return None, None, None, None, None, None, None
        else:
            logging.warning("Invalid experiment type. Please enter 'fiber' or 'cath'.")