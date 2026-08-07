# Safety

BioMed-RAGS is a research platform containing motorized equipment, electrical components, and optical radiation sources. It must be operated only by trained personnel following the applicable institutional risk assessment, local safety procedures, and manufacturer instructions.

The information in this document does not replace source-specific laser or UV safety assessment, laboratory training, or equipment manuals.

## Main hazards

The principal hazards include:

- Direct or reflected exposure to laser or ultraviolet radiation
- Eye or skin exposure during alignment, mounting, or testing
- Pinch, impact, and entanglement hazards from the robotic arm, linear rail, and rotational stages
- Unexpected motion caused by incorrect coordinates, units, limits, or software configuration
- Electrical hazards from power supplies, controllers, motors, and modified wiring
- Movement or release of an incorrectly secured specimen, detector, fixture, or cable

## Before operation

Before starting a measurement:

1. Identify the wavelength, optical power, operating mode, and hazard classification of the installed source.
2. Complete a risk assessment appropriate to the source and experimental configuration.
3. Restrict access to the measurement area as required by laboratory procedures.
4. Inspect the robot, rail, stages, fixtures, fasteners, wiring, and cables for damage or insecure connections.
5. Confirm that the specimen and detector are securely mounted.
6. Verify the coordinate system, scan limits, step direction, standoff distance, and expected motion.
7. Perform a low-speed dry run with the optical source disabled.
8. Confirm that an accessible method is available to stop motion and disconnect power.
9. Remove loose objects from the motion area and secure loose clothing, hair, and cables.
10. Do not leave the operating system unattended unless the laboratory risk assessment explicitly permits it.

## Optical radiation safety

The demonstrated applications include a 405 nm diode laser and measurements involving 222 nm excimer lamps. Direct or reflected optical radiation may cause eye or skin injury. Far-UVC radiation must not be assumed to be harmless.

Apply controls appropriate to the installed source, which may include:

- Enclosing or shielding the optical path
- Terminating beams with a suitable beam stop
- Preventing unintended reflections
- Restricting access during operation
- Using interlocks where required
- Monitoring the experiment remotely
- Wearing eye or skin protection selected for the wavelength and exposure level

Protective eyewear must have a wavelength range and optical density appropriate to the specific source. Eyewear does not replace enclosure, shielding, access control, or other engineering controls.

Switch off or otherwise make the optical source safe before installing, removing, or adjusting a specimen or detector. Alignment with an active source should be performed only under an approved alignment procedure.

## Robotic and mechanical safety

The robotic arm, linear rail, and rotational stages can create pinch, impact, and entanglement hazards.

- Keep hands and other objects outside the motion envelope while the system is enabled.
- Disable motion and disconnect power before adjusting fixtures or mechanical components.
- Do not exceed the travel, speed, payload, or operating limits specified by the equipment manufacturers.
- Secure specimens at both ends before operating the rotational stages.
- Route cables so they cannot become trapped, stretched, or wound around moving components.
- Use conservative speeds during setup and after any hardware or software change.

The demonstrated rotational stages operate open loop. A missed motor step may not be detected automatically. Verify the mechanical reference position before a scan and after any unexpected interruption or collision.

## Software and motion configuration

Software limits are not physical guards.

Before enabling automated motion:

- Check that all coordinates use the intended units and reference frame.
- Confirm minimum and maximum positions for every axis.
- Check the sign and direction of each step value.
- Confirm that the programmed path cannot contact the specimen, fixtures, optical table, or nearby equipment.
- Test the stop procedure before the first active measurement.
- Repeat the dry run after changing fixtures, detectors, scan geometry, or control software.

Stop the system immediately if movement differs from the expected path.

## Electrical safety

- Disconnect power before modifying wiring or electronics.
- Do not operate the system with exposed conductors or damaged cables.
- Use suitable power supplies, protective enclosures, connectors, strain relief, and overcurrent protection.
- Follow the grounding and installation requirements provided by each equipment manufacturer.
- Electrical modifications should be performed only by personnel qualified for the work.

## Incident response

If unintended exposure, collision, electrical failure, mechanical damage, or abnormal motion occurs:

1. Stop motion and disable the optical source.
2. Disconnect power when it is safe to do so.
3. Prevent further access to the affected equipment.
4. Follow the laboratory incident and medical-response procedures.
5. Inspect and revalidate the system before returning it to operation.

Report safety-related repository issues without including personal, confidential, or security-sensitive information.
