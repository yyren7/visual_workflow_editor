# -*- coding : UTF-8 -*-
import time, json, os, sys, importlib, signal, copy, pickle
# To use globals var
from lib.utility.constant import DM, EM, R, MR, LR, CR, T
from lib.utility.common_globals import L, RD1, RAC
from lib.utility.auto_globals import error_yaml, number_param_yaml, initial_number_param_yaml, flag_param_yaml
from lib.utility.constant import TEACH_FILE_PATH, NUMBER_PARAM_FILE_PATH, FLAG_PARAM_FILE_PATH, ERROR_FILE_PATH
from lib.utility.tcp_client import TCPClient
from lib.plc.plc_base_class import BasePLC
# To use laddar func
import lib.utility.functions as func
import lib.utility.drive as drive
import lib.utility.helper as helper
# To read sidebar
import lib.sidebar.teaching as teach
import lib.sidebar.number_parameter as num_param
import lib.sidebar.robot_io as rb_io
import lib.sidebar.contec_io as c_io
def signal_handler(sig, frame):
  if(RAC.connected): RAC.send_command('stopRobot()')
  func.cleanup()
  sys.exit(0)

if os.name == 'nt':
  signal.signal(signal.SIGBREAK, signal_handler) 
elif os.name == 'posix':
  signal.signal(signal.SIGTERM, signal_handler) 

ERROR_INTERVAL = 1

success = False
start_time = x = y = z = rx = ry = rz = vel = acc = dec = dist = stime = tool = 0
override = 100
pallet_settings = {}
pallet_offset = [{'x': 0.0, 'y': 0.0, 'z': 0.0} for _ in range(10)]
current_pos = {'x': 0.0, 'y': 0.0, 'z': 0.0,'rx': 0.0, 'ry': 0.0, 'rz': 0.0}
plc_connected = [False for _ in range(10)]
plc_instance = [{'R_DM': None, 'MR_EM': None} for _ in range(10)]
camera_responded  = [False for _ in range(10)]
camera_connected = [False for _ in range(10)]
camera_instance = [None for _ in range(10)]
camera_results = [{'test': 0, 'x': 0.0, 'y': 0.0, 'r': 0.0, 'text': ''} for _ in range(10)]
external_io_connected = [False for _ in range(10)]
external_io_instance = [None for _ in range(10)]
robot_status = {'servo': False, 'origin': False, 'arrived': False, 'error': False, 'error_id': 0, 'current_pos': [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],'input_signal': [False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False]}

func.get_device_data()
auto_status = 'AUTO MODE.'
L.EM_relay[0:0+len(helper.name_to_ascii16(auto_status, 40))] = helper.name_to_ascii16(auto_status, 40)

if __name__ == '__main__':
  while True:
    try:
      #print('Auto program is running...')
      func.send_device_data()
      time.sleep(0.001)
      drive.create_cycle_timer()
      drive.handle_system_variable()
      drive.handle_system_lamp()
      drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      L.updateTime()
      L.ldlg = 0x0
      L.aax  = 0x0 
      L.trlg = 0x0 
      L.iix  = 0x01
      func.get_command()

      #;Process:procedures_defnoreturn@5
      L.LD(L.local_MR['seq_step[17]']['name'], L.local_MR['seq_step[17]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2000]']['name'], L.local_MR['seq_step[2000]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[0]']['name'], L.local_MR['seq_step[0]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.ANPB(L.local_MR['seq_step[0]']['name'], L.local_MR['seq_step[0]']['addr'])
      L.OR(L.local_MR['seq_step[2000]']['name'], L.local_MR['seq_step[2000]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2000]']['name'], L.local_MR['seq_step[2000]']['addr'])
      #;Post-Process:procedures_defnoreturn@5

      #;Process:moveP@6
      L.LD(L.local_MR['seq_step[2000]']['name'], L.local_MR['seq_step[2000]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2001]']['name'], L.local_MR['seq_step[2001]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1]']['name'], L.local_MR['seq_step[1]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[1]']['name'], L.local_T['move_static_timer[1]']['addr'])
      L.ANPB(L.local_MR['seq_step[1]']['name'], L.local_MR['seq_step[1]']['addr'])
      L.OR(L.local_MR['seq_step[2001]']['name'], L.local_MR['seq_step[2001]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2001]']['name'], L.local_MR['seq_step[2001]']['addr'])
      #;Post-Process:moveP@6
      #;timeout:moveP@6
      L.LD(L.local_MR['seq_step[1]']['name'], L.local_MR['seq_step[1]']['addr'])
      L.TMS(L.local_T['block_timeout[1]']['addr'], 60000000)
      L.LDP(L.local_T['block_timeout[1]']['name'], L.local_T['block_timeout[1]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+1, message='moveP@6:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+1, error_yaml=error_yaml)
      #;error:moveP@6
      L.LD(L.local_MR['seq_step[1]']['name'], L.local_MR['seq_step[1]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+1, message=f"moveP@6:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+1, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+1, message='moveP@6:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+1, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+1, message='moveP@6:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+1, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@6
      L.LDP(L.local_MR['seq_step[1]']['name'], L.local_MR['seq_step[1]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(653.55, -364.396, 342.632, -178.328, -0.418, -41.248, 100.0, 100.0, 100.0, 5.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, override)
        RAC.send_command(f'moveAbsolutePtp({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')
      L.LD(L.local_MR['seq_step[1]']['name'], L.local_MR['seq_step[1]']['addr'])
      L.ANB(L.local_MR['seq_step[2001]']['name'], L.local_MR['seq_step[2001]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')
      L.LD(L.local_MR['seq_step[1]']['name'], L.local_MR['seq_step[1]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[1]']['addr'], 0.0)

      #;Process:moveP@15
      L.LD(L.local_MR['seq_step[2001]']['name'], L.local_MR['seq_step[2001]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2002]']['name'], L.local_MR['seq_step[2002]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2]']['name'], L.local_MR['seq_step[2]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[2]']['name'], L.local_T['move_static_timer[2]']['addr'])
      L.ANPB(L.local_MR['seq_step[2]']['name'], L.local_MR['seq_step[2]']['addr'])
      L.OR(L.local_MR['seq_step[2002]']['name'], L.local_MR['seq_step[2002]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2002]']['name'], L.local_MR['seq_step[2002]']['addr'])
      #;Post-Process:moveP@15
      #;timeout:moveP@15
      L.LD(L.local_MR['seq_step[2]']['name'], L.local_MR['seq_step[2]']['addr'])
      L.TMS(L.local_T['block_timeout[2]']['addr'], 60000000)
      L.LDP(L.local_T['block_timeout[2]']['name'], L.local_T['block_timeout[2]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+2, message='moveP@15:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+2, error_yaml=error_yaml)
      #;error:moveP@15
      L.LD(L.local_MR['seq_step[2]']['name'], L.local_MR['seq_step[2]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+2, message=f"moveP@15:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+2, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((10.0 == 0) or (10.0 == 0) or (10.0 == 0)):
          drive.register_error(no=801+2, message='moveP@15:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+2, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+2, message='moveP@15:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+2, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@15
      L.LDP(L.local_MR['seq_step[2]']['name'], L.local_MR['seq_step[2]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(625.929, -38.22, 326.541, -178.278, 0.292, -45.666, 10.0, 10.0, 10.0, 5.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, override)
        RAC.send_command(f'moveAbsolutePtp({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')
      L.LD(L.local_MR['seq_step[2]']['name'], L.local_MR['seq_step[2]']['addr'])
      L.ANB(L.local_MR['seq_step[2002]']['name'], L.local_MR['seq_step[2002]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')
      L.LD(L.local_MR['seq_step[2]']['name'], L.local_MR['seq_step[2]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[2]']['addr'], 0.0)

      #;Process:procedures_callnoreturn@8
      L.LD(L.local_MR['seq_step[2002]']['name'], L.local_MR['seq_step[2002]']['addr'])
      L.MPS()
      L.LDB(L.local_MR['seq_step[2003]']['name'], L.local_MR['seq_step[2003]']['addr'])
      L.ANB(L.local_MR['seq_step[2068]']['name'], L.local_MR['seq_step[2068]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[3]']['name'], L.local_MR['seq_step[3]']['addr'])
      L.MPP()
      L.LD(L.local_MR['seq_step[2068]']['name'], L.local_MR['seq_step[2068]']['addr'])
      L.ANPB(L.local_MR['seq_step[3]']['name'], L.local_MR['seq_step[3]']['addr'])
      L.OR(L.local_MR['seq_step[2003]']['name'], L.local_MR['seq_step[2003]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2003]']['name'], L.local_MR['seq_step[2003]']['addr'])
      #;Post-Process:procedures_callnoreturn@8

      #;Process:moveP@16
      L.LD(L.local_MR['seq_step[2003]']['name'], L.local_MR['seq_step[2003]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2004]']['name'], L.local_MR['seq_step[2004]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[4]']['name'], L.local_MR['seq_step[4]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[4]']['name'], L.local_T['move_static_timer[4]']['addr'])
      L.ANPB(L.local_MR['seq_step[4]']['name'], L.local_MR['seq_step[4]']['addr'])
      L.OR(L.local_MR['seq_step[2004]']['name'], L.local_MR['seq_step[2004]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2004]']['name'], L.local_MR['seq_step[2004]']['addr'])
      #;Post-Process:moveP@16
      #;timeout:moveP@16
      L.LD(L.local_MR['seq_step[4]']['name'], L.local_MR['seq_step[4]']['addr'])
      L.TMS(L.local_T['block_timeout[4]']['addr'], 60000000)
      L.LDP(L.local_T['block_timeout[4]']['name'], L.local_T['block_timeout[4]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+4, message='moveP@16:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+4, error_yaml=error_yaml)
      #;error:moveP@16
      L.LD(L.local_MR['seq_step[4]']['name'], L.local_MR['seq_step[4]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+4, message=f"moveP@16:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+4, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((10.0 == 0) or (10.0 == 0) or (10.0 == 0)):
          drive.register_error(no=801+4, message='moveP@16:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+4, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+4, message='moveP@16:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+4, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@16
      L.LDP(L.local_MR['seq_step[4]']['name'], L.local_MR['seq_step[4]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(625.929, -38.22, 294.931, -178.278, 0.292, -45.666, 10.0, 10.0, 10.0, 0.2, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, override)
        RAC.send_command(f'moveAbsolutePtp({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')
      L.LD(L.local_MR['seq_step[4]']['name'], L.local_MR['seq_step[4]']['addr'])
      L.ANB(L.local_MR['seq_step[2004]']['name'], L.local_MR['seq_step[2004]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')
      L.LD(L.local_MR['seq_step[4]']['name'], L.local_MR['seq_step[4]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[4]']['addr'], 0.0)

      #;Process:procedures_callnoreturn@9
      L.LD(L.local_MR['seq_step[2004]']['name'], L.local_MR['seq_step[2004]']['addr'])
      L.MPS()
      L.LDB(L.local_MR['seq_step[2005]']['name'], L.local_MR['seq_step[2005]']['addr'])
      L.ANB(L.local_MR['seq_step[2072]']['name'], L.local_MR['seq_step[2072]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[5]']['name'], L.local_MR['seq_step[5]']['addr'])
      L.MPP()
      L.LD(L.local_MR['seq_step[2072]']['name'], L.local_MR['seq_step[2072]']['addr'])
      L.ANPB(L.local_MR['seq_step[5]']['name'], L.local_MR['seq_step[5]']['addr'])
      L.OR(L.local_MR['seq_step[2005]']['name'], L.local_MR['seq_step[2005]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2005]']['name'], L.local_MR['seq_step[2005]']['addr'])
      #;Post-Process:procedures_callnoreturn@9

      #;Process:moveP@56
      L.LD(L.local_MR['seq_step[2005]']['name'], L.local_MR['seq_step[2005]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2006]']['name'], L.local_MR['seq_step[2006]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[6]']['name'], L.local_MR['seq_step[6]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[6]']['name'], L.local_T['move_static_timer[6]']['addr'])
      L.ANPB(L.local_MR['seq_step[6]']['name'], L.local_MR['seq_step[6]']['addr'])
      L.OR(L.local_MR['seq_step[2006]']['name'], L.local_MR['seq_step[2006]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2006]']['name'], L.local_MR['seq_step[2006]']['addr'])
      #;Post-Process:moveP@56
      #;timeout:moveP@56
      L.LD(L.local_MR['seq_step[6]']['name'], L.local_MR['seq_step[6]']['addr'])
      L.TMS(L.local_T['block_timeout[6]']['addr'], 60000000)
      L.LDP(L.local_T['block_timeout[6]']['name'], L.local_T['block_timeout[6]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+6, message='moveP@56:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+6, error_yaml=error_yaml)
      #;error:moveP@56
      L.LD(L.local_MR['seq_step[6]']['name'], L.local_MR['seq_step[6]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+6, message=f"moveP@56:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+6, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((10.0 == 0) or (10.0 == 0) or (10.0 == 0)):
          drive.register_error(no=801+6, message='moveP@56:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+6, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+6, message='moveP@56:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+6, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@56
      L.LDP(L.local_MR['seq_step[6]']['name'], L.local_MR['seq_step[6]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(625.929, -38.224, 324.963, -178.278, 0.293, -45.668, 10.0, 10.0, 10.0, 5.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, override)
        RAC.send_command(f'moveAbsolutePtp({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')
      L.LD(L.local_MR['seq_step[6]']['name'], L.local_MR['seq_step[6]']['addr'])
      L.ANB(L.local_MR['seq_step[2006]']['name'], L.local_MR['seq_step[2006]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')
      L.LD(L.local_MR['seq_step[6]']['name'], L.local_MR['seq_step[6]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[6]']['addr'], 0.0)

      #;Process:moveP@57
      L.LD(L.local_MR['seq_step[2006]']['name'], L.local_MR['seq_step[2006]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2007]']['name'], L.local_MR['seq_step[2007]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[7]']['name'], L.local_MR['seq_step[7]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[7]']['name'], L.local_T['move_static_timer[7]']['addr'])
      L.ANPB(L.local_MR['seq_step[7]']['name'], L.local_MR['seq_step[7]']['addr'])
      L.OR(L.local_MR['seq_step[2007]']['name'], L.local_MR['seq_step[2007]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2007]']['name'], L.local_MR['seq_step[2007]']['addr'])
      #;Post-Process:moveP@57
      #;timeout:moveP@57
      L.LD(L.local_MR['seq_step[7]']['name'], L.local_MR['seq_step[7]']['addr'])
      L.TMS(L.local_T['block_timeout[7]']['addr'], 60000000)
      L.LDP(L.local_T['block_timeout[7]']['name'], L.local_T['block_timeout[7]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+7, message='moveP@57:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+7, error_yaml=error_yaml)
      #;error:moveP@57
      L.LD(L.local_MR['seq_step[7]']['name'], L.local_MR['seq_step[7]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+7, message=f"moveP@57:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+7, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((10.0 == 0) or (10.0 == 0) or (10.0 == 0)):
          drive.register_error(no=801+7, message='moveP@57:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+7, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+7, message='moveP@57:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+7, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@57
      L.LDP(L.local_MR['seq_step[7]']['name'], L.local_MR['seq_step[7]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(625.928, -88.35, 324.956, -178.279, 0.293, -45.669, 10.0, 10.0, 10.0, 5.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, override)
        RAC.send_command(f'moveAbsolutePtp({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')
      L.LD(L.local_MR['seq_step[7]']['name'], L.local_MR['seq_step[7]']['addr'])
      L.ANB(L.local_MR['seq_step[2007]']['name'], L.local_MR['seq_step[2007]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')
      L.LD(L.local_MR['seq_step[7]']['name'], L.local_MR['seq_step[7]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[7]']['addr'], 0.0)

      #;Process:moveP@21
      L.LD(L.local_MR['seq_step[2007]']['name'], L.local_MR['seq_step[2007]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2008]']['name'], L.local_MR['seq_step[2008]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[8]']['name'], L.local_MR['seq_step[8]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[8]']['name'], L.local_T['move_static_timer[8]']['addr'])
      L.ANPB(L.local_MR['seq_step[8]']['name'], L.local_MR['seq_step[8]']['addr'])
      L.OR(L.local_MR['seq_step[2008]']['name'], L.local_MR['seq_step[2008]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2008]']['name'], L.local_MR['seq_step[2008]']['addr'])
      #;Post-Process:moveP@21
      #;timeout:moveP@21
      L.LD(L.local_MR['seq_step[8]']['name'], L.local_MR['seq_step[8]']['addr'])
      L.TMS(L.local_T['block_timeout[8]']['addr'], 60000000)
      L.LDP(L.local_T['block_timeout[8]']['name'], L.local_T['block_timeout[8]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+8, message='moveP@21:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+8, error_yaml=error_yaml)
      #;error:moveP@21
      L.LD(L.local_MR['seq_step[8]']['name'], L.local_MR['seq_step[8]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+8, message=f"moveP@21:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+8, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+8, message='moveP@21:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+8, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+8, message='moveP@21:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+8, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@21
      L.LDP(L.local_MR['seq_step[8]']['name'], L.local_MR['seq_step[8]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(653.55, -364.396, 342.632, -178.328, -0.418, -41.248, 100.0, 100.0, 100.0, 5.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, override)
        RAC.send_command(f'moveAbsolutePtp({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')
      L.LD(L.local_MR['seq_step[8]']['name'], L.local_MR['seq_step[8]']['addr'])
      L.ANB(L.local_MR['seq_step[2008]']['name'], L.local_MR['seq_step[2008]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')
      L.LD(L.local_MR['seq_step[8]']['name'], L.local_MR['seq_step[8]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[8]']['addr'], 0.0)


      #;Process:procedures_defnoreturn@14
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2009]']['name'], L.local_MR['seq_step[2009]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[9]']['name'], L.local_MR['seq_step[9]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.ANPB(L.local_MR['seq_step[9]']['name'], L.local_MR['seq_step[9]']['addr'])
      L.OR(L.local_MR['seq_step[2009]']['name'], L.local_MR['seq_step[2009]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2009]']['name'], L.local_MR['seq_step[2009]']['addr'])
      #;Post-Process:procedures_defnoreturn@14

      #;Process:wait_input@5
      L.LD(L.local_MR['seq_step[2009]']['name'], L.local_MR['seq_step[2009]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2010]']['name'], L.local_MR['seq_step[2010]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[10]']['name'], L.local_MR['seq_step[10]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(True if robot_status['input_signal'][12] else False)
      L.ANPB(L.local_MR['seq_step[10]']['name'], L.local_MR['seq_step[10]']['addr'])
      L.OR(L.local_MR['seq_step[2010]']['name'], L.local_MR['seq_step[2010]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2010]']['name'], L.local_MR['seq_step[2010]']['addr'])
      #;timeout:wait_input@5
      L.LD(L.local_MR['seq_step[10]']['name'], L.local_MR['seq_step[10]']['addr'])
      L.TMS(L.local_T['block_timeout[10]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[10]']['name'], L.local_T['block_timeout[10]']['addr'])
      if (L.aax & L.iix):
        drive.register_error(no=801+10, message='wait_input@5:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+10, error_yaml=error_yaml)
      #;action:wait_input@5
      L.LD(L.local_MR['seq_step[10]']['name'], L.local_MR['seq_step[10]']['addr'])
      if (L.aax & L.iix):
        RAC.send_command('getInput(12)')


      #;Process:select_robot@1
      L.LD(L.local_R['program_start[0]']['name'], L.local_R['program_start[0]']['addr'])
      L.MPS()
      L.LDB(L.local_MR['seq_step[2011]']['name'], L.local_MR['seq_step[2011]']['addr'])
      L.ANB(RAC.connected)
      L.ANL()
      L.OUT(L.local_MR['seq_step[11]']['name'], L.local_MR['seq_step[11]']['addr'])
      L.MPP()
      L.LD(RAC.connected)
      L.OR(L.local_MR['seq_step[2011]']['name'], L.local_MR['seq_step[2011]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2011]']['name'], L.local_MR['seq_step[2011]']['addr'])
      #;Post-Process:select_robot@1
      #;timeout:select_robot@1
      L.LD(L.local_MR['seq_step[11]']['name'], L.local_MR['seq_step[11]']['addr'])
      L.TMS(L.local_T['block_timeout[11]']['addr'], 600000)
      L.LDP(L.local_T['block_timeout[11]']['name'], L.local_T['block_timeout[11]']['addr'])
      if (L.aax & L.iix):
        drive.register_error(no=801+11, message='select_robot@1:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+11, error_yaml=error_yaml)
      #;action:select_robot@1
      if(RAC.connected):
        RAC.send_command('getRobotStatus()')
        RAC.send_command('updateRedis()')
        robot_status = RAC.get_status()
        drive.handle_auto_sidebar(robot_status)
        L.LD(MR, 307)
        if (L.aax & L.iix):
          RAC.send_command('resetError()')
        L.LD(MR, 304)
        if (L.aax & L.iix):
          RAC.send_command('stopRobot()')
        flag_param_yaml['F480']['value'] = L.getRelay(MR, 300)
        flag_param_yaml['F481']['value'] = L.getRelay(MR, 302)
        flag_param_yaml['F482']['value'] = L.getRelay(MR, 304)
        flag_param_yaml['F483']['value'] = L.getRelay(MR, 501)
        flag_param_yaml['F484']['value'] = L.getRelay(MR, 307)
        if robot_status['current_pos']:
          current_pos['x'] = robot_status['current_pos'][0]
          current_pos['y'] = robot_status['current_pos'][1]
          current_pos['z'] = robot_status['current_pos'][2]
          current_pos['rx'] = robot_status['current_pos'][3]
          current_pos['ry'] = robot_status['current_pos'][4]
          current_pos['rz'] = robot_status['current_pos'][5]
      else:
        RAC.send_command('getRobotStatus()')

      #;Process:set_motor@1
      L.LD(L.local_MR['seq_step[2011]']['name'], L.local_MR['seq_step[2011]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2012]']['name'], L.local_MR['seq_step[2012]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[12]']['name'], L.local_MR['seq_step[12]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(L.local_MR['servo_success[0]']['name'], L.local_MR['servo_success[0]']['addr'])
      L.AND(robot_status['servo'])
      L.OR(L.local_MR['seq_step[2012]']['name'], L.local_MR['seq_step[2012]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2012]']['name'], L.local_MR['seq_step[2012]']['addr'])
      #;Post-Process:set_motor@1
      #;timeout:set_motor@1
      L.LD(L.local_MR['seq_step[12]']['name'], L.local_MR['seq_step[12]']['addr'])
      L.TMS(L.local_T['block_timeout[12]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[12]']['name'], L.local_T['block_timeout[12]']['addr'])
      if (L.aax & L.iix):
        drive.register_error(no=801+12, message='set_motor@1:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+12, error_yaml=error_yaml)
      #;action:set_motor@1
      L.LD(L.local_MR['seq_step[12]']['name'], L.local_MR['seq_step[12]']['addr'])
      L.ANB(L.local_MR['servo_success[0]']['name'], L.local_MR['servo_success[0]']['addr'])
      if (L.aax & L.iix):
        success = RAC.send_command('setServoOn()')
        if (success): L.setRelay(L.local_MR['servo_success[0]']['name'], L.local_MR['servo_success[0]']['addr'])
        else        : L.resetRelay(L.local_MR['servo_success[0]']['name'], L.local_MR['servo_success[0]']['addr'])

      #;Process:set_number@1
      L.LD(L.local_MR['seq_step[2012]']['name'], L.local_MR['seq_step[2012]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2013]']['name'], L.local_MR['seq_step[2013]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[13]']['name'], L.local_MR['seq_step[13]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.ANPB(L.local_MR['seq_step[13]']['name'], L.local_MR['seq_step[13]']['addr'])
      L.OR(L.local_MR['seq_step[2013]']['name'], L.local_MR['seq_step[2013]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2013]']['name'], L.local_MR['seq_step[2013]']['addr'])
      #;Post-Process:set_number@1
      #;timeout:set_number@1
      L.LD(L.local_MR['seq_step[13]']['name'], L.local_MR['seq_step[13]']['addr'])
      L.TMS(L.local_T['block_timeout[13]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[13]']['name'], L.local_T['block_timeout[13]']['addr'])
      if (L.aax & L.iix):
        drive.register_error(no=801+13, message='set_number@1:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+13, error_yaml=error_yaml)
      #;action:set_number@1
      L.LDP(L.local_MR['seq_step[13]']['name'], L.local_MR['seq_step[13]']['addr'])
      if (L.aax & L.iix):
        number_param_yaml['N5']['value'] = 2

      #;Process:loop@1
      L.LD(L.local_MR['seq_step[2013]']['name'], L.local_MR['seq_step[2013]']['addr'])
      L.ANB(L.local_MR['seq_step[2031]']['name'], L.local_MR['seq_step[2031]']['addr'])
      L.MPS()
      L.ANB(L.local_MR['seq_step[2014]']['name'], L.local_MR['seq_step[2014]']['addr'])
      L.OUT(L.local_MR['seq_step[14]']['name'], L.local_MR['seq_step[14]']['addr'])
      L.MPP()
      L.LDPB(L.local_MR['seq_step[14]']['name'], L.local_MR['seq_step[14]']['addr'])
      L.OR(L.local_MR['seq_step[2014]']['name'], L.local_MR['seq_step[2014]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2014]']['name'], L.local_MR['seq_step[2014]']['addr'])
      #;Post-Process:loop@1
      #;action:loop@1
      L.LD(L.local_MR['seq_step[14]']['name'], L.local_MR['seq_step[14]']['addr'])
      if (L.aax & L.iix):
        start_time = time.perf_counter()

      #;Pre-Process:controls_if@1
      #;Process:controls_if@1
      L.LD(L.local_MR['seq_step[2014]']['name'], L.local_MR['seq_step[2014]']['addr'])
      L.MPS()
      L.ANB(L.local_MR['seq_step[2015]']['name'], L.local_MR['seq_step[2015]']['addr'])
      L.OUT(L.local_MR['seq_step[15]']['name'], L.local_MR['seq_step[15]']['addr'])
      L.MPP()
      L.LD(True if ((number_param_yaml['N5']['value'] == 2)) else False)
      L.OR(L.local_MR['seq_step[2015]']['name'], L.local_MR['seq_step[2015]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2015]']['name'], L.local_MR['seq_step[2015]']['addr'])

      #;Process:moveP@1
      L.LD(L.local_MR['seq_step[2015]']['name'], L.local_MR['seq_step[2015]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2016]']['name'], L.local_MR['seq_step[2016]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[16]']['name'], L.local_MR['seq_step[16]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[16]']['name'], L.local_T['move_static_timer[16]']['addr'])
      L.ANPB(L.local_MR['seq_step[16]']['name'], L.local_MR['seq_step[16]']['addr'])
      L.OR(L.local_MR['seq_step[2016]']['name'], L.local_MR['seq_step[2016]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2016]']['name'], L.local_MR['seq_step[2016]']['addr'])
      #;Post-Process:moveP@1
      #;timeout:moveP@1
      L.LD(L.local_MR['seq_step[16]']['name'], L.local_MR['seq_step[16]']['addr'])
      L.TMS(L.local_T['block_timeout[16]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[16]']['name'], L.local_T['block_timeout[16]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+16, message='moveP@1:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+16, error_yaml=error_yaml)
      #;error:moveP@1
      L.LD(L.local_MR['seq_step[16]']['name'], L.local_MR['seq_step[16]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+16, message=f"moveP@1:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+16, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+16, message='moveP@1:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+16, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+16, message='moveP@1:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+16, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@1
      L.LDP(L.local_MR['seq_step[16]']['name'], L.local_MR['seq_step[16]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(172.402, -366.352, 311.891, 178.93, 0.583, -136.958, 100.0, 100.0, 100.0, 5.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, override)
        RAC.send_command(f'moveAbsolutePtp({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')
      L.LD(L.local_MR['seq_step[16]']['name'], L.local_MR['seq_step[16]']['addr'])
      L.ANB(L.local_MR['seq_step[2016]']['name'], L.local_MR['seq_step[2016]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')
      L.LD(L.local_MR['seq_step[16]']['name'], L.local_MR['seq_step[16]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[16]']['addr'], 0.0)

      #;Process:procedures_callnoreturn@11
      L.LD(L.local_MR['seq_step[2016]']['name'], L.local_MR['seq_step[2016]']['addr'])
      L.MPS()
      L.LDB(L.local_MR['seq_step[2017]']['name'], L.local_MR['seq_step[2017]']['addr'])
      L.ANB(L.local_MR['seq_step[2008]']['name'], L.local_MR['seq_step[2008]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[17]']['name'], L.local_MR['seq_step[17]']['addr'])
      L.MPP()
      L.LD(L.local_MR['seq_step[2008]']['name'], L.local_MR['seq_step[2008]']['addr'])
      L.ANPB(L.local_MR['seq_step[17]']['name'], L.local_MR['seq_step[17]']['addr'])
      L.OR(L.local_MR['seq_step[2017]']['name'], L.local_MR['seq_step[2017]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2017]']['name'], L.local_MR['seq_step[2017]']['addr'])
      #;Post-Process:procedures_callnoreturn@11

      #;Process:moveP@53
      L.LD(L.local_MR['seq_step[2017]']['name'], L.local_MR['seq_step[2017]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2018]']['name'], L.local_MR['seq_step[2018]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[18]']['name'], L.local_MR['seq_step[18]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[18]']['name'], L.local_T['move_static_timer[18]']['addr'])
      L.ANPB(L.local_MR['seq_step[18]']['name'], L.local_MR['seq_step[18]']['addr'])
      L.OR(L.local_MR['seq_step[2018]']['name'], L.local_MR['seq_step[2018]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2018]']['name'], L.local_MR['seq_step[2018]']['addr'])
      #;Post-Process:moveP@53
      #;timeout:moveP@53
      L.LD(L.local_MR['seq_step[18]']['name'], L.local_MR['seq_step[18]']['addr'])
      L.TMS(L.local_T['block_timeout[18]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[18]']['name'], L.local_T['block_timeout[18]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+18, message='moveP@53:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+18, error_yaml=error_yaml)
      #;error:moveP@53
      L.LD(L.local_MR['seq_step[18]']['name'], L.local_MR['seq_step[18]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+18, message=f"moveP@53:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+18, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+18, message='moveP@53:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+18, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+18, message='moveP@53:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+18, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@53
      L.LDP(L.local_MR['seq_step[18]']['name'], L.local_MR['seq_step[18]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(172.402, -366.352, 311.891, 178.93, 0.583, -136.958, 100.0, 100.0, 100.0, 5.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, override)
        RAC.send_command(f'moveAbsolutePtp({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')
      L.LD(L.local_MR['seq_step[18]']['name'], L.local_MR['seq_step[18]']['addr'])
      L.ANB(L.local_MR['seq_step[2018]']['name'], L.local_MR['seq_step[2018]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')
      L.LD(L.local_MR['seq_step[18]']['name'], L.local_MR['seq_step[18]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[18]']['addr'], 0.0)

      #;Process:procedures_callnoreturn@12
      L.LD(L.local_MR['seq_step[2018]']['name'], L.local_MR['seq_step[2018]']['addr'])
      L.MPS()
      L.LDB(L.local_MR['seq_step[2019]']['name'], L.local_MR['seq_step[2019]']['addr'])
      L.ANB(L.local_MR['seq_step[2041]']['name'], L.local_MR['seq_step[2041]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[19]']['name'], L.local_MR['seq_step[19]']['addr'])
      L.MPP()
      L.LD(L.local_MR['seq_step[2041]']['name'], L.local_MR['seq_step[2041]']['addr'])
      L.ANPB(L.local_MR['seq_step[19]']['name'], L.local_MR['seq_step[19]']['addr'])
      L.OR(L.local_MR['seq_step[2019]']['name'], L.local_MR['seq_step[2019]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2019]']['name'], L.local_MR['seq_step[2019]']['addr'])
      #;Post-Process:procedures_callnoreturn@12

      #;Process:moveP@14
      L.LD(L.local_MR['seq_step[2019]']['name'], L.local_MR['seq_step[2019]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2020]']['name'], L.local_MR['seq_step[2020]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[20]']['name'], L.local_MR['seq_step[20]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[20]']['name'], L.local_T['move_static_timer[20]']['addr'])
      L.ANPB(L.local_MR['seq_step[20]']['name'], L.local_MR['seq_step[20]']['addr'])
      L.OR(L.local_MR['seq_step[2020]']['name'], L.local_MR['seq_step[2020]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2020]']['name'], L.local_MR['seq_step[2020]']['addr'])
      #;Post-Process:moveP@14
      #;timeout:moveP@14
      L.LD(L.local_MR['seq_step[20]']['name'], L.local_MR['seq_step[20]']['addr'])
      L.TMS(L.local_T['block_timeout[20]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[20]']['name'], L.local_T['block_timeout[20]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+20, message='moveP@14:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+20, error_yaml=error_yaml)
      #;error:moveP@14
      L.LD(L.local_MR['seq_step[20]']['name'], L.local_MR['seq_step[20]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+20, message=f"moveP@14:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+20, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+20, message='moveP@14:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+20, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+20, message='moveP@14:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+20, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@14
      L.LDP(L.local_MR['seq_step[20]']['name'], L.local_MR['seq_step[20]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(172.402, -366.352, 311.891, 178.93, 0.583, -136.958, 100.0, 100.0, 100.0, 5.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, override)
        RAC.send_command(f'moveAbsolutePtp({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')
      L.LD(L.local_MR['seq_step[20]']['name'], L.local_MR['seq_step[20]']['addr'])
      L.ANB(L.local_MR['seq_step[2020]']['name'], L.local_MR['seq_step[2020]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')
      L.LD(L.local_MR['seq_step[20]']['name'], L.local_MR['seq_step[20]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[20]']['addr'], 0.0)

      #;Process:moveP@43
      L.LD(L.local_MR['seq_step[2020]']['name'], L.local_MR['seq_step[2020]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2021]']['name'], L.local_MR['seq_step[2021]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[21]']['name'], L.local_MR['seq_step[21]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[21]']['name'], L.local_T['move_static_timer[21]']['addr'])
      L.ANPB(L.local_MR['seq_step[21]']['name'], L.local_MR['seq_step[21]']['addr'])
      L.OR(L.local_MR['seq_step[2021]']['name'], L.local_MR['seq_step[2021]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2021]']['name'], L.local_MR['seq_step[2021]']['addr'])
      #;Post-Process:moveP@43
      #;timeout:moveP@43
      L.LD(L.local_MR['seq_step[21]']['name'], L.local_MR['seq_step[21]']['addr'])
      L.TMS(L.local_T['block_timeout[21]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[21]']['name'], L.local_T['block_timeout[21]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+21, message='moveP@43:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+21, error_yaml=error_yaml)
      #;error:moveP@43
      L.LD(L.local_MR['seq_step[21]']['name'], L.local_MR['seq_step[21]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+21, message=f"moveP@43:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+21, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+21, message='moveP@43:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+21, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+21, message='moveP@43:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+21, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@43
      L.LDP(L.local_MR['seq_step[21]']['name'], L.local_MR['seq_step[21]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(-126.434, -280.319, 361.422, -178.908, 0.419, -46.383, 100.0, 100.0, 100.0, 5.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, override)
        RAC.send_command(f'moveAbsolutePtp({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')
      L.LD(L.local_MR['seq_step[21]']['name'], L.local_MR['seq_step[21]']['addr'])
      L.ANB(L.local_MR['seq_step[2021]']['name'], L.local_MR['seq_step[2021]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')
      L.LD(L.local_MR['seq_step[21]']['name'], L.local_MR['seq_step[21]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[21]']['addr'], 0.0)

      #;Process:procedures_callnoreturn@15
      L.LD(L.local_MR['seq_step[2021]']['name'], L.local_MR['seq_step[2021]']['addr'])
      L.MPS()
      L.LDB(L.local_MR['seq_step[2022]']['name'], L.local_MR['seq_step[2022]']['addr'])
      L.ANB(L.local_MR['seq_step[2064]']['name'], L.local_MR['seq_step[2064]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[22]']['name'], L.local_MR['seq_step[22]']['addr'])
      L.MPP()
      L.LD(L.local_MR['seq_step[2064]']['name'], L.local_MR['seq_step[2064]']['addr'])
      L.ANPB(L.local_MR['seq_step[22]']['name'], L.local_MR['seq_step[22]']['addr'])
      L.OR(L.local_MR['seq_step[2022]']['name'], L.local_MR['seq_step[2022]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2022]']['name'], L.local_MR['seq_step[2022]']['addr'])
      #;Post-Process:procedures_callnoreturn@15

      #;Process:wait_timer@6
      L.LD(L.local_MR['seq_step[2022]']['name'], L.local_MR['seq_step[2022]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2023]']['name'], L.local_MR['seq_step[2023]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[23]']['name'], L.local_MR['seq_step[23]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(L.local_T['block_timer1[23]']['name'], L.local_T['block_timer1[23]']['addr'])
      L.OR(L.local_MR['seq_step[2023]']['name'], L.local_MR['seq_step[2023]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2023]']['name'], L.local_MR['seq_step[2023]']['addr'])
      #;Post-Process:wait_timer@6
      #;timeout:wait_timer@6
      L.LD(L.local_MR['seq_step[23]']['name'], L.local_MR['seq_step[23]']['addr'])
      L.TMS(L.local_T['block_timeout[23]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[23]']['name'], L.local_T['block_timeout[23]']['addr'])
      if (L.aax & L.iix):
        drive.register_error(no=801+23, message='wait_timer@6:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+23, error_yaml=error_yaml)
      #;action:wait_timer@6
      L.LD(L.local_MR['seq_step[23]']['name'], L.local_MR['seq_step[23]']['addr'])
      L.TMS(L.local_T['block_timer1[23]']['addr'], wait_msec=number_param_yaml['N483']['value'])

      #;Process:procedures_callnoreturn@16
      L.LD(L.local_MR['seq_step[2023]']['name'], L.local_MR['seq_step[2023]']['addr'])
      L.MPS()
      L.LDB(L.local_MR['seq_step[2024]']['name'], L.local_MR['seq_step[2024]']['addr'])
      L.ANB(L.local_MR['seq_step[2080]']['name'], L.local_MR['seq_step[2080]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[24]']['name'], L.local_MR['seq_step[24]']['addr'])
      L.MPP()
      L.LD(L.local_MR['seq_step[2080]']['name'], L.local_MR['seq_step[2080]']['addr'])
      L.ANPB(L.local_MR['seq_step[24]']['name'], L.local_MR['seq_step[24]']['addr'])
      L.OR(L.local_MR['seq_step[2024]']['name'], L.local_MR['seq_step[2024]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2024]']['name'], L.local_MR['seq_step[2024]']['addr'])
      #;Post-Process:procedures_callnoreturn@16

      #;Process:moveP@28
      L.LD(L.local_MR['seq_step[2024]']['name'], L.local_MR['seq_step[2024]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2025]']['name'], L.local_MR['seq_step[2025]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[25]']['name'], L.local_MR['seq_step[25]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[25]']['name'], L.local_T['move_static_timer[25]']['addr'])
      L.ANPB(L.local_MR['seq_step[25]']['name'], L.local_MR['seq_step[25]']['addr'])
      L.OR(L.local_MR['seq_step[2025]']['name'], L.local_MR['seq_step[2025]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2025]']['name'], L.local_MR['seq_step[2025]']['addr'])
      #;Post-Process:moveP@28
      #;timeout:moveP@28
      L.LD(L.local_MR['seq_step[25]']['name'], L.local_MR['seq_step[25]']['addr'])
      L.TMS(L.local_T['block_timeout[25]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[25]']['name'], L.local_T['block_timeout[25]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+25, message='moveP@28:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+25, error_yaml=error_yaml)
      #;error:moveP@28
      L.LD(L.local_MR['seq_step[25]']['name'], L.local_MR['seq_step[25]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+25, message=f"moveP@28:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+25, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+25, message='moveP@28:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+25, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+25, message='moveP@28:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+25, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@28
      L.LDP(L.local_MR['seq_step[25]']['name'], L.local_MR['seq_step[25]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(172.402, -366.352, 311.891, 178.93, 0.583, -136.958, 100.0, 100.0, 100.0, 5.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, override)
        RAC.send_command(f'moveAbsolutePtp({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')
      L.LD(L.local_MR['seq_step[25]']['name'], L.local_MR['seq_step[25]']['addr'])
      L.ANB(L.local_MR['seq_step[2025]']['name'], L.local_MR['seq_step[2025]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')
      L.LD(L.local_MR['seq_step[25]']['name'], L.local_MR['seq_step[25]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[25]']['addr'], 0.0)

      #;Process:procedures_callnoreturn@17
      L.LD(L.local_MR['seq_step[2025]']['name'], L.local_MR['seq_step[2025]']['addr'])
      L.MPS()
      L.LDB(L.local_MR['seq_step[2026]']['name'], L.local_MR['seq_step[2026]']['addr'])
      L.ANB(L.local_MR['seq_step[2088]']['name'], L.local_MR['seq_step[2088]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[26]']['name'], L.local_MR['seq_step[26]']['addr'])
      L.MPP()
      L.LD(L.local_MR['seq_step[2088]']['name'], L.local_MR['seq_step[2088]']['addr'])
      L.ANPB(L.local_MR['seq_step[26]']['name'], L.local_MR['seq_step[26]']['addr'])
      L.OR(L.local_MR['seq_step[2026]']['name'], L.local_MR['seq_step[2026]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2026]']['name'], L.local_MR['seq_step[2026]']['addr'])
      #;Post-Process:procedures_callnoreturn@17

      #;Process:procedures_callnoreturn@18
      L.LD(L.local_MR['seq_step[2026]']['name'], L.local_MR['seq_step[2026]']['addr'])
      L.MPS()
      L.LDB(L.local_MR['seq_step[2027]']['name'], L.local_MR['seq_step[2027]']['addr'])
      L.ANB(L.local_MR['seq_step[2096]']['name'], L.local_MR['seq_step[2096]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[27]']['name'], L.local_MR['seq_step[27]']['addr'])
      L.MPP()
      L.LD(L.local_MR['seq_step[2096]']['name'], L.local_MR['seq_step[2096]']['addr'])
      L.ANPB(L.local_MR['seq_step[27]']['name'], L.local_MR['seq_step[27]']['addr'])
      L.OR(L.local_MR['seq_step[2027]']['name'], L.local_MR['seq_step[2027]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2027]']['name'], L.local_MR['seq_step[2027]']['addr'])
      #;Post-Process:procedures_callnoreturn@18

      #;Process:procedures_callnoreturn@19
      L.LD(L.local_MR['seq_step[2027]']['name'], L.local_MR['seq_step[2027]']['addr'])
      L.MPS()
      L.LDB(L.local_MR['seq_step[2028]']['name'], L.local_MR['seq_step[2028]']['addr'])
      L.ANB(L.local_MR['seq_step[2103]']['name'], L.local_MR['seq_step[2103]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[28]']['name'], L.local_MR['seq_step[28]']['addr'])
      L.MPP()
      L.LD(L.local_MR['seq_step[2103]']['name'], L.local_MR['seq_step[2103]']['addr'])
      L.ANPB(L.local_MR['seq_step[28]']['name'], L.local_MR['seq_step[28]']['addr'])
      L.OR(L.local_MR['seq_step[2028]']['name'], L.local_MR['seq_step[2028]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2028]']['name'], L.local_MR['seq_step[2028]']['addr'])
      #;Post-Process:procedures_callnoreturn@19

      #;Process:procedures_callnoreturn@20
      L.LD(L.local_MR['seq_step[2028]']['name'], L.local_MR['seq_step[2028]']['addr'])
      L.MPS()
      L.LDB(L.local_MR['seq_step[2029]']['name'], L.local_MR['seq_step[2029]']['addr'])
      L.ANB(L.local_MR['seq_step[2112]']['name'], L.local_MR['seq_step[2112]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[29]']['name'], L.local_MR['seq_step[29]']['addr'])
      L.MPP()
      L.LD(L.local_MR['seq_step[2112]']['name'], L.local_MR['seq_step[2112]']['addr'])
      L.ANPB(L.local_MR['seq_step[29]']['name'], L.local_MR['seq_step[29]']['addr'])
      L.OR(L.local_MR['seq_step[2029]']['name'], L.local_MR['seq_step[2029]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2029]']['name'], L.local_MR['seq_step[2029]']['addr'])
      #;Post-Process:procedures_callnoreturn@20

      #;Process:procedures_callnoreturn@21
      L.LD(L.local_MR['seq_step[2029]']['name'], L.local_MR['seq_step[2029]']['addr'])
      L.MPS()
      L.LDB(L.local_MR['seq_step[2030]']['name'], L.local_MR['seq_step[2030]']['addr'])
      L.ANB(L.local_MR['seq_step[2119]']['name'], L.local_MR['seq_step[2119]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[30]']['name'], L.local_MR['seq_step[30]']['addr'])
      L.MPP()
      L.LD(L.local_MR['seq_step[2119]']['name'], L.local_MR['seq_step[2119]']['addr'])
      L.ANPB(L.local_MR['seq_step[30]']['name'], L.local_MR['seq_step[30]']['addr'])
      L.OR(L.local_MR['seq_step[2030]']['name'], L.local_MR['seq_step[2030]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2030]']['name'], L.local_MR['seq_step[2030]']['addr'])
      #;Post-Process:procedures_callnoreturn@21

      #;Process:return@2
      L.LD(L.local_MR['seq_step[2030]']['name'], L.local_MR['seq_step[2030]']['addr'])
      L.MPS()
      L.ANB(L.local_MR['seq_step[2031]']['name'], L.local_MR['seq_step[2031]']['addr'])
      L.OUT(L.local_MR['seq_step[31]']['name'], L.local_MR['seq_step[31]']['addr'])
      L.MPP()
      L.LDPB(L.local_MR['seq_step[31]']['name'], L.local_MR['seq_step[31]']['addr'])
      L.OR(L.local_MR['seq_step[2031]']['name'], L.local_MR['seq_step[2031]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2031]']['name'], L.local_MR['seq_step[2031]']['addr'])
      #;Post-Process:return@2
      #;action:return@2
      L.LDP(L.local_MR['seq_step[31]']['name'], L.local_MR['seq_step[31]']['addr'])
      if (L.aax & L.iix):
        elapsed_time = int((time.perf_counter() - start_time) * 1000)
        L.EM_relay[2020:2020+len(helper.int32_to_uint16s(elapsed_time))] = helper.int32_to_uint16s(elapsed_time)











      #;Process:procedures_defnoreturn@6
      L.LD(L.local_MR['seq_step[19]']['name'], L.local_MR['seq_step[19]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2032]']['name'], L.local_MR['seq_step[2032]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[32]']['name'], L.local_MR['seq_step[32]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.ANPB(L.local_MR['seq_step[32]']['name'], L.local_MR['seq_step[32]']['addr'])
      L.OR(L.local_MR['seq_step[2032]']['name'], L.local_MR['seq_step[2032]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2032]']['name'], L.local_MR['seq_step[2032]']['addr'])
      #;Post-Process:procedures_defnoreturn@6

      #;Process:moveP@17
      L.LD(L.local_MR['seq_step[2032]']['name'], L.local_MR['seq_step[2032]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2033]']['name'], L.local_MR['seq_step[2033]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[33]']['name'], L.local_MR['seq_step[33]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[33]']['name'], L.local_T['move_static_timer[33]']['addr'])
      L.ANPB(L.local_MR['seq_step[33]']['name'], L.local_MR['seq_step[33]']['addr'])
      L.OR(L.local_MR['seq_step[2033]']['name'], L.local_MR['seq_step[2033]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2033]']['name'], L.local_MR['seq_step[2033]']['addr'])
      #;Post-Process:moveP@17
      #;timeout:moveP@17
      L.LD(L.local_MR['seq_step[33]']['name'], L.local_MR['seq_step[33]']['addr'])
      L.TMS(L.local_T['block_timeout[33]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[33]']['name'], L.local_T['block_timeout[33]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+33, message='moveP@17:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+33, error_yaml=error_yaml)
      #;error:moveP@17
      L.LD(L.local_MR['seq_step[33]']['name'], L.local_MR['seq_step[33]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+33, message=f"moveP@17:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+33, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+33, message='moveP@17:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+33, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+33, message='moveP@17:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+33, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@17
      L.LDP(L.local_MR['seq_step[33]']['name'], L.local_MR['seq_step[33]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(172.402, -366.352, 311.891, 178.93, 0.583, -136.958, 100.0, 100.0, 100.0, 5.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, override)
        RAC.send_command(f'moveAbsolutePtp({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')
      L.LD(L.local_MR['seq_step[33]']['name'], L.local_MR['seq_step[33]']['addr'])
      L.ANB(L.local_MR['seq_step[2033]']['name'], L.local_MR['seq_step[2033]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')
      L.LD(L.local_MR['seq_step[33]']['name'], L.local_MR['seq_step[33]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[33]']['addr'], 0.0)

      #;Process:moveP@2
      L.LD(L.local_MR['seq_step[2033]']['name'], L.local_MR['seq_step[2033]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2034]']['name'], L.local_MR['seq_step[2034]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[34]']['name'], L.local_MR['seq_step[34]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[34]']['name'], L.local_T['move_static_timer[34]']['addr'])
      L.ANPB(L.local_MR['seq_step[34]']['name'], L.local_MR['seq_step[34]']['addr'])
      L.OR(L.local_MR['seq_step[2034]']['name'], L.local_MR['seq_step[2034]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2034]']['name'], L.local_MR['seq_step[2034]']['addr'])
      #;Post-Process:moveP@2
      #;timeout:moveP@2
      L.LD(L.local_MR['seq_step[34]']['name'], L.local_MR['seq_step[34]']['addr'])
      L.TMS(L.local_T['block_timeout[34]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[34]']['name'], L.local_T['block_timeout[34]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+34, message='moveP@2:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+34, error_yaml=error_yaml)
      #;error:moveP@2
      L.LD(L.local_MR['seq_step[34]']['name'], L.local_MR['seq_step[34]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+34, message=f"moveP@2:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+34, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+34, message='moveP@2:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+34, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+34, message='moveP@2:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+34, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@2
      L.LDP(L.local_MR['seq_step[34]']['name'], L.local_MR['seq_step[34]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(518.464, -328.691, 226.47, 177.79, 4.062, 135.558, 100.0, 100.0, 100.0, 5.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, override)
        RAC.send_command(f'moveAbsolutePtp({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')
      L.LD(L.local_MR['seq_step[34]']['name'], L.local_MR['seq_step[34]']['addr'])
      L.ANB(L.local_MR['seq_step[2034]']['name'], L.local_MR['seq_step[2034]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')
      L.LD(L.local_MR['seq_step[34]']['name'], L.local_MR['seq_step[34]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[34]']['addr'], 0.0)

      #;Process:moveP@3
      L.LD(L.local_MR['seq_step[2034]']['name'], L.local_MR['seq_step[2034]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2035]']['name'], L.local_MR['seq_step[2035]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[35]']['name'], L.local_MR['seq_step[35]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[35]']['name'], L.local_T['move_static_timer[35]']['addr'])
      L.ANPB(L.local_MR['seq_step[35]']['name'], L.local_MR['seq_step[35]']['addr'])
      L.OR(L.local_MR['seq_step[2035]']['name'], L.local_MR['seq_step[2035]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2035]']['name'], L.local_MR['seq_step[2035]']['addr'])
      #;Post-Process:moveP@3
      #;timeout:moveP@3
      L.LD(L.local_MR['seq_step[35]']['name'], L.local_MR['seq_step[35]']['addr'])
      L.TMS(L.local_T['block_timeout[35]']['addr'], 60000000)
      L.LDP(L.local_T['block_timeout[35]']['name'], L.local_T['block_timeout[35]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+35, message='moveP@3:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+35, error_yaml=error_yaml)
      #;error:moveP@3
      L.LD(L.local_MR['seq_step[35]']['name'], L.local_MR['seq_step[35]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+35, message=f"moveP@3:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+35, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+35, message='moveP@3:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+35, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+35, message='moveP@3:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+35, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@3
      L.LDP(L.local_MR['seq_step[35]']['name'], L.local_MR['seq_step[35]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(734.349, -310.173, 115.976, -179.914, -0.641, 134.837, 100.0, 100.0, 100.0, 5.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, override)
        RAC.send_command(f'moveAbsolutePtp({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')
      L.LD(L.local_MR['seq_step[35]']['name'], L.local_MR['seq_step[35]']['addr'])
      L.ANB(L.local_MR['seq_step[2035]']['name'], L.local_MR['seq_step[2035]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')
      L.LD(L.local_MR['seq_step[35]']['name'], L.local_MR['seq_step[35]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[35]']['addr'], 0.0)

      #;Process:procedures_callnoreturn@1
      L.LD(L.local_MR['seq_step[2035]']['name'], L.local_MR['seq_step[2035]']['addr'])
      L.MPS()
      L.LDB(L.local_MR['seq_step[2036]']['name'], L.local_MR['seq_step[2036]']['addr'])
      L.ANB(L.local_MR['seq_step[2045]']['name'], L.local_MR['seq_step[2045]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[36]']['name'], L.local_MR['seq_step[36]']['addr'])
      L.MPP()
      L.LD(L.local_MR['seq_step[2045]']['name'], L.local_MR['seq_step[2045]']['addr'])
      L.ANPB(L.local_MR['seq_step[36]']['name'], L.local_MR['seq_step[36]']['addr'])
      L.OR(L.local_MR['seq_step[2036]']['name'], L.local_MR['seq_step[2036]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2036]']['name'], L.local_MR['seq_step[2036]']['addr'])
      #;Post-Process:procedures_callnoreturn@1

      #;Process:moveP@4
      L.LD(L.local_MR['seq_step[2036]']['name'], L.local_MR['seq_step[2036]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2037]']['name'], L.local_MR['seq_step[2037]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[37]']['name'], L.local_MR['seq_step[37]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[37]']['name'], L.local_T['move_static_timer[37]']['addr'])
      L.ANPB(L.local_MR['seq_step[37]']['name'], L.local_MR['seq_step[37]']['addr'])
      L.OR(L.local_MR['seq_step[2037]']['name'], L.local_MR['seq_step[2037]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2037]']['name'], L.local_MR['seq_step[2037]']['addr'])
      #;Post-Process:moveP@4
      #;timeout:moveP@4
      L.LD(L.local_MR['seq_step[37]']['name'], L.local_MR['seq_step[37]']['addr'])
      L.TMS(L.local_T['block_timeout[37]']['addr'], 60000000)
      L.LDP(L.local_T['block_timeout[37]']['name'], L.local_T['block_timeout[37]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+37, message='moveP@4:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+37, error_yaml=error_yaml)
      #;error:moveP@4
      L.LD(L.local_MR['seq_step[37]']['name'], L.local_MR['seq_step[37]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+37, message=f"moveP@4:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+37, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((10.0 == 0) or (10.0 == 0) or (10.0 == 0)):
          drive.register_error(no=801+37, message='moveP@4:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+37, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+37, message='moveP@4:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+37, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@4
      L.LDP(L.local_MR['seq_step[37]']['name'], L.local_MR['seq_step[37]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(734.34, -310.134, 65.796, -179.911, -0.648, 134.837, 10.0, 10.0, 10.0, 0.2, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, override)
        RAC.send_command(f'moveAbsolutePtp({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')
      L.LD(L.local_MR['seq_step[37]']['name'], L.local_MR['seq_step[37]']['addr'])
      L.ANB(L.local_MR['seq_step[2037]']['name'], L.local_MR['seq_step[2037]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')
      L.LD(L.local_MR['seq_step[37]']['name'], L.local_MR['seq_step[37]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[37]']['addr'], 0.0)

      #;Process:wait_timer@1
      L.LD(L.local_MR['seq_step[2037]']['name'], L.local_MR['seq_step[2037]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2038]']['name'], L.local_MR['seq_step[2038]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[38]']['name'], L.local_MR['seq_step[38]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(L.local_T['block_timer1[38]']['name'], L.local_T['block_timer1[38]']['addr'])
      L.OR(L.local_MR['seq_step[2038]']['name'], L.local_MR['seq_step[2038]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2038]']['name'], L.local_MR['seq_step[2038]']['addr'])
      #;Post-Process:wait_timer@1
      #;timeout:wait_timer@1
      L.LD(L.local_MR['seq_step[38]']['name'], L.local_MR['seq_step[38]']['addr'])
      L.TMS(L.local_T['block_timeout[38]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[38]']['name'], L.local_T['block_timeout[38]']['addr'])
      if (L.aax & L.iix):
        drive.register_error(no=801+38, message='wait_timer@1:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+38, error_yaml=error_yaml)
      #;action:wait_timer@1
      L.LD(L.local_MR['seq_step[38]']['name'], L.local_MR['seq_step[38]']['addr'])
      L.TMS(L.local_T['block_timer1[38]']['addr'], wait_msec=number_param_yaml['N483']['value'])

      #;Process:procedures_callnoreturn@2
      L.LD(L.local_MR['seq_step[2038]']['name'], L.local_MR['seq_step[2038]']['addr'])
      L.MPS()
      L.LDB(L.local_MR['seq_step[2039]']['name'], L.local_MR['seq_step[2039]']['addr'])
      L.ANB(L.local_MR['seq_step[2049]']['name'], L.local_MR['seq_step[2049]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[39]']['name'], L.local_MR['seq_step[39]']['addr'])
      L.MPP()
      L.LD(L.local_MR['seq_step[2049]']['name'], L.local_MR['seq_step[2049]']['addr'])
      L.ANPB(L.local_MR['seq_step[39]']['name'], L.local_MR['seq_step[39]']['addr'])
      L.OR(L.local_MR['seq_step[2039]']['name'], L.local_MR['seq_step[2039]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2039]']['name'], L.local_MR['seq_step[2039]']['addr'])
      #;Post-Process:procedures_callnoreturn@2

      #;Process:moveP@5
      L.LD(L.local_MR['seq_step[2039]']['name'], L.local_MR['seq_step[2039]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2040]']['name'], L.local_MR['seq_step[2040]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[40]']['name'], L.local_MR['seq_step[40]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[40]']['name'], L.local_T['move_static_timer[40]']['addr'])
      L.ANPB(L.local_MR['seq_step[40]']['name'], L.local_MR['seq_step[40]']['addr'])
      L.OR(L.local_MR['seq_step[2040]']['name'], L.local_MR['seq_step[2040]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2040]']['name'], L.local_MR['seq_step[2040]']['addr'])
      #;Post-Process:moveP@5
      #;timeout:moveP@5
      L.LD(L.local_MR['seq_step[40]']['name'], L.local_MR['seq_step[40]']['addr'])
      L.TMS(L.local_T['block_timeout[40]']['addr'], 60000000)
      L.LDP(L.local_T['block_timeout[40]']['name'], L.local_T['block_timeout[40]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+40, message='moveP@5:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+40, error_yaml=error_yaml)
      #;error:moveP@5
      L.LD(L.local_MR['seq_step[40]']['name'], L.local_MR['seq_step[40]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+40, message=f"moveP@5:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+40, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+40, message='moveP@5:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+40, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+40, message='moveP@5:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+40, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@5
      L.LDP(L.local_MR['seq_step[40]']['name'], L.local_MR['seq_step[40]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(734.349, -310.173, 115.976, -179.914, -0.641, 134.837, 100.0, 100.0, 100.0, 5.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, override)
        RAC.send_command(f'moveAbsolutePtp({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')
      L.LD(L.local_MR['seq_step[40]']['name'], L.local_MR['seq_step[40]']['addr'])
      L.ANB(L.local_MR['seq_step[2040]']['name'], L.local_MR['seq_step[2040]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')
      L.LD(L.local_MR['seq_step[40]']['name'], L.local_MR['seq_step[40]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[40]']['addr'], 0.0)

      #;Process:moveP@18
      L.LD(L.local_MR['seq_step[2040]']['name'], L.local_MR['seq_step[2040]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2041]']['name'], L.local_MR['seq_step[2041]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[41]']['name'], L.local_MR['seq_step[41]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[41]']['name'], L.local_T['move_static_timer[41]']['addr'])
      L.ANPB(L.local_MR['seq_step[41]']['name'], L.local_MR['seq_step[41]']['addr'])
      L.OR(L.local_MR['seq_step[2041]']['name'], L.local_MR['seq_step[2041]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2041]']['name'], L.local_MR['seq_step[2041]']['addr'])
      #;Post-Process:moveP@18
      #;timeout:moveP@18
      L.LD(L.local_MR['seq_step[41]']['name'], L.local_MR['seq_step[41]']['addr'])
      L.TMS(L.local_T['block_timeout[41]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[41]']['name'], L.local_T['block_timeout[41]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+41, message='moveP@18:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+41, error_yaml=error_yaml)
      #;error:moveP@18
      L.LD(L.local_MR['seq_step[41]']['name'], L.local_MR['seq_step[41]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+41, message=f"moveP@18:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+41, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+41, message='moveP@18:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+41, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+41, message='moveP@18:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+41, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@18
      L.LDP(L.local_MR['seq_step[41]']['name'], L.local_MR['seq_step[41]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(518.464, -328.691, 226.47, 177.79, 4.062, 135.558, 100.0, 100.0, 100.0, 5.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, override)
        RAC.send_command(f'moveAbsolutePtp({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')
      L.LD(L.local_MR['seq_step[41]']['name'], L.local_MR['seq_step[41]']['addr'])
      L.ANB(L.local_MR['seq_step[2041]']['name'], L.local_MR['seq_step[2041]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')
      L.LD(L.local_MR['seq_step[41]']['name'], L.local_MR['seq_step[41]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[41]']['addr'], 0.0)


      #;Process:procedures_defnoreturn@1
      L.LD(L.local_MR['seq_step[36]']['name'], L.local_MR['seq_step[36]']['addr'])
      L.OR(L.local_MR['seq_step[54]']['name'], L.local_MR['seq_step[54]']['addr'])
      L.OR(L.local_MR['seq_step[85]']['name'], L.local_MR['seq_step[85]']['addr'])
      L.OR(L.local_MR['seq_step[116]']['name'], L.local_MR['seq_step[116]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2042]']['name'], L.local_MR['seq_step[2042]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[42]']['name'], L.local_MR['seq_step[42]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.ANPB(L.local_MR['seq_step[42]']['name'], L.local_MR['seq_step[42]']['addr'])
      L.OR(L.local_MR['seq_step[2042]']['name'], L.local_MR['seq_step[2042]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2042]']['name'], L.local_MR['seq_step[2042]']['addr'])
      #;Post-Process:procedures_defnoreturn@1

      #;Process:wait_timer@3
      L.LD(L.local_MR['seq_step[2042]']['name'], L.local_MR['seq_step[2042]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2043]']['name'], L.local_MR['seq_step[2043]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[43]']['name'], L.local_MR['seq_step[43]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(L.local_T['block_timer1[43]']['name'], L.local_T['block_timer1[43]']['addr'])
      L.OR(L.local_MR['seq_step[2043]']['name'], L.local_MR['seq_step[2043]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2043]']['name'], L.local_MR['seq_step[2043]']['addr'])
      #;Post-Process:wait_timer@3
      #;timeout:wait_timer@3
      L.LD(L.local_MR['seq_step[43]']['name'], L.local_MR['seq_step[43]']['addr'])
      L.TMS(L.local_T['block_timeout[43]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[43]']['name'], L.local_T['block_timeout[43]']['addr'])
      if (L.aax & L.iix):
        drive.register_error(no=801+43, message='wait_timer@3:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+43, error_yaml=error_yaml)
      #;action:wait_timer@3
      L.LD(L.local_MR['seq_step[43]']['name'], L.local_MR['seq_step[43]']['addr'])
      L.TMS(L.local_T['block_timer1[43]']['addr'], wait_msec=number_param_yaml['N483']['value'])

      #;Process:set_output@1
      L.LD(L.local_MR['seq_step[2043]']['name'], L.local_MR['seq_step[2043]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2044]']['name'], L.local_MR['seq_step[2044]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[44]']['name'], L.local_MR['seq_step[44]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(L.local_MR['robot_io_success[0]']['name'], L.local_MR['robot_io_success[0]']['addr'])
      L.ANPB(L.local_MR['seq_step[44]']['name'], L.local_MR['seq_step[44]']['addr'])
      L.OR(L.local_MR['seq_step[2044]']['name'], L.local_MR['seq_step[2044]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2044]']['name'], L.local_MR['seq_step[2044]']['addr'])
      #;Post-Process:set_output@1
      #;timeout:set_output@1
      L.LD(L.local_MR['seq_step[44]']['name'], L.local_MR['seq_step[44]']['addr'])
      L.TMS(L.local_T['block_timeout[44]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[44]']['name'], L.local_T['block_timeout[44]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+44, message='set_output@1:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+44, error_yaml=error_yaml)
      L.LD(L.local_MR['seq_step[44]']['name'], L.local_MR['seq_step[44]']['addr'])
      L.ANB(L.local_MR['robot_io_success[0]']['name'], L.local_MR['robot_io_success[0]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        success = RAC.send_command('setOutputON(1)')
        if (success): L.setRelay(L.local_MR['robot_io_success[0]']['name'], L.local_MR['robot_io_success[0]']['addr'])
        else        : L.resetRelay(L.local_MR['robot_io_success[0]']['name'], L.local_MR['robot_io_success[0]']['addr'])
      L.LDP(L.local_MR['seq_step[2044]']['name'], L.local_MR['seq_step[2044]']['addr'])
      if (L.aax & L.iix):
        L.resetRelay(L.local_MR['robot_io_success[0]']['name'], L.local_MR['robot_io_success[0]']['addr'])

      #;Process:wait_input@3
      L.LD(L.local_MR['seq_step[2044]']['name'], L.local_MR['seq_step[2044]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2045]']['name'], L.local_MR['seq_step[2045]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[45]']['name'], L.local_MR['seq_step[45]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(True if robot_status['input_signal'][0] else False)
      L.ANPB(L.local_MR['seq_step[45]']['name'], L.local_MR['seq_step[45]']['addr'])
      L.OR(L.local_MR['seq_step[2045]']['name'], L.local_MR['seq_step[2045]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2045]']['name'], L.local_MR['seq_step[2045]']['addr'])
      #;timeout:wait_input@3
      L.LD(L.local_MR['seq_step[45]']['name'], L.local_MR['seq_step[45]']['addr'])
      L.TMS(L.local_T['block_timeout[45]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[45]']['name'], L.local_T['block_timeout[45]']['addr'])
      if (L.aax & L.iix):
        drive.register_error(no=801+45, message='wait_input@3:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+45, error_yaml=error_yaml)
      #;action:wait_input@3
      L.LD(L.local_MR['seq_step[45]']['name'], L.local_MR['seq_step[45]']['addr'])
      if (L.aax & L.iix):
        RAC.send_command('getInput(0)')


      #;Process:procedures_defnoreturn@2
      L.LD(L.local_MR['seq_step[39]']['name'], L.local_MR['seq_step[39]']['addr'])
      L.OR(L.local_MR['seq_step[77]']['name'], L.local_MR['seq_step[77]']['addr'])
      L.OR(L.local_MR['seq_step[108]']['name'], L.local_MR['seq_step[108]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2046]']['name'], L.local_MR['seq_step[2046]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[46]']['name'], L.local_MR['seq_step[46]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.ANPB(L.local_MR['seq_step[46]']['name'], L.local_MR['seq_step[46]']['addr'])
      L.OR(L.local_MR['seq_step[2046]']['name'], L.local_MR['seq_step[2046]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2046]']['name'], L.local_MR['seq_step[2046]']['addr'])
      #;Post-Process:procedures_defnoreturn@2

      #;Process:wait_timer@2
      L.LD(L.local_MR['seq_step[2046]']['name'], L.local_MR['seq_step[2046]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2047]']['name'], L.local_MR['seq_step[2047]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[47]']['name'], L.local_MR['seq_step[47]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(L.local_T['block_timer1[47]']['name'], L.local_T['block_timer1[47]']['addr'])
      L.OR(L.local_MR['seq_step[2047]']['name'], L.local_MR['seq_step[2047]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2047]']['name'], L.local_MR['seq_step[2047]']['addr'])
      #;Post-Process:wait_timer@2
      #;timeout:wait_timer@2
      L.LD(L.local_MR['seq_step[47]']['name'], L.local_MR['seq_step[47]']['addr'])
      L.TMS(L.local_T['block_timeout[47]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[47]']['name'], L.local_T['block_timeout[47]']['addr'])
      if (L.aax & L.iix):
        drive.register_error(no=801+47, message='wait_timer@2:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+47, error_yaml=error_yaml)
      #;action:wait_timer@2
      L.LD(L.local_MR['seq_step[47]']['name'], L.local_MR['seq_step[47]']['addr'])
      L.TMS(L.local_T['block_timer1[47]']['addr'], wait_msec=number_param_yaml['N482']['value'])

      #;Process:set_output@2
      L.LD(L.local_MR['seq_step[2047]']['name'], L.local_MR['seq_step[2047]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2048]']['name'], L.local_MR['seq_step[2048]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[48]']['name'], L.local_MR['seq_step[48]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(L.local_MR['robot_io_success[0]']['name'], L.local_MR['robot_io_success[0]']['addr'])
      L.ANPB(L.local_MR['seq_step[48]']['name'], L.local_MR['seq_step[48]']['addr'])
      L.OR(L.local_MR['seq_step[2048]']['name'], L.local_MR['seq_step[2048]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2048]']['name'], L.local_MR['seq_step[2048]']['addr'])
      #;Post-Process:set_output@2
      #;timeout:set_output@2
      L.LD(L.local_MR['seq_step[48]']['name'], L.local_MR['seq_step[48]']['addr'])
      L.TMS(L.local_T['block_timeout[48]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[48]']['name'], L.local_T['block_timeout[48]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+48, message='set_output@2:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+48, error_yaml=error_yaml)
      L.LD(L.local_MR['seq_step[48]']['name'], L.local_MR['seq_step[48]']['addr'])
      L.ANB(L.local_MR['robot_io_success[0]']['name'], L.local_MR['robot_io_success[0]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        success = RAC.send_command('setOutputOFF(1)')
        if (success): L.setRelay(L.local_MR['robot_io_success[0]']['name'], L.local_MR['robot_io_success[0]']['addr'])
        else        : L.resetRelay(L.local_MR['robot_io_success[0]']['name'], L.local_MR['robot_io_success[0]']['addr'])
      L.LDP(L.local_MR['seq_step[2048]']['name'], L.local_MR['seq_step[2048]']['addr'])
      if (L.aax & L.iix):
        L.resetRelay(L.local_MR['robot_io_success[0]']['name'], L.local_MR['robot_io_success[0]']['addr'])

      #;Process:wait_input@2
      L.LD(L.local_MR['seq_step[2048]']['name'], L.local_MR['seq_step[2048]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2049]']['name'], L.local_MR['seq_step[2049]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[49]']['name'], L.local_MR['seq_step[49]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(True if robot_status['input_signal'][1] else False)
      L.ANPB(L.local_MR['seq_step[49]']['name'], L.local_MR['seq_step[49]']['addr'])
      L.OR(L.local_MR['seq_step[2049]']['name'], L.local_MR['seq_step[2049]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2049]']['name'], L.local_MR['seq_step[2049]']['addr'])
      #;timeout:wait_input@2
      L.LD(L.local_MR['seq_step[49]']['name'], L.local_MR['seq_step[49]']['addr'])
      L.TMS(L.local_T['block_timeout[49]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[49]']['name'], L.local_T['block_timeout[49]']['addr'])
      if (L.aax & L.iix):
        drive.register_error(no=801+49, message='wait_input@2:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+49, error_yaml=error_yaml)
      #;action:wait_input@2
      L.LD(L.local_MR['seq_step[49]']['name'], L.local_MR['seq_step[49]']['addr'])
      if (L.aax & L.iix):
        RAC.send_command('getInput(1)')


      #;Process:procedures_defnoreturn@7
      L.LD(L.local_MR['seq_step[22]']['name'], L.local_MR['seq_step[22]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2050]']['name'], L.local_MR['seq_step[2050]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[50]']['name'], L.local_MR['seq_step[50]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.ANPB(L.local_MR['seq_step[50]']['name'], L.local_MR['seq_step[50]']['addr'])
      L.OR(L.local_MR['seq_step[2050]']['name'], L.local_MR['seq_step[2050]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2050]']['name'], L.local_MR['seq_step[2050]']['addr'])
      #;Post-Process:procedures_defnoreturn@7

      #;Process:moveP@7
      L.LD(L.local_MR['seq_step[2050]']['name'], L.local_MR['seq_step[2050]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2051]']['name'], L.local_MR['seq_step[2051]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[51]']['name'], L.local_MR['seq_step[51]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[51]']['name'], L.local_T['move_static_timer[51]']['addr'])
      L.ANPB(L.local_MR['seq_step[51]']['name'], L.local_MR['seq_step[51]']['addr'])
      L.OR(L.local_MR['seq_step[2051]']['name'], L.local_MR['seq_step[2051]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2051]']['name'], L.local_MR['seq_step[2051]']['addr'])
      #;Post-Process:moveP@7
      #;timeout:moveP@7
      L.LD(L.local_MR['seq_step[51]']['name'], L.local_MR['seq_step[51]']['addr'])
      L.TMS(L.local_T['block_timeout[51]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[51]']['name'], L.local_T['block_timeout[51]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+51, message='moveP@7:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+51, error_yaml=error_yaml)
      #;error:moveP@7
      L.LD(L.local_MR['seq_step[51]']['name'], L.local_MR['seq_step[51]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+51, message=f"moveP@7:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+51, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+51, message='moveP@7:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+51, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+51, message='moveP@7:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+51, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@7
      L.LDP(L.local_MR['seq_step[51]']['name'], L.local_MR['seq_step[51]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(-126.434, -280.319, 361.422, -178.908, 0.419, -46.383, 100.0, 100.0, 100.0, 5.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, override)
        RAC.send_command(f'moveAbsolutePtp({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')
      L.LD(L.local_MR['seq_step[51]']['name'], L.local_MR['seq_step[51]']['addr'])
      L.ANB(L.local_MR['seq_step[2051]']['name'], L.local_MR['seq_step[2051]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')
      L.LD(L.local_MR['seq_step[51]']['name'], L.local_MR['seq_step[51]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[51]']['addr'], 0.0)

      #;Process:moveP@8
      L.LD(L.local_MR['seq_step[2051]']['name'], L.local_MR['seq_step[2051]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2052]']['name'], L.local_MR['seq_step[2052]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[52]']['name'], L.local_MR['seq_step[52]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[52]']['name'], L.local_T['move_static_timer[52]']['addr'])
      L.ANPB(L.local_MR['seq_step[52]']['name'], L.local_MR['seq_step[52]']['addr'])
      L.OR(L.local_MR['seq_step[2052]']['name'], L.local_MR['seq_step[2052]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2052]']['name'], L.local_MR['seq_step[2052]']['addr'])
      #;Post-Process:moveP@8
      #;timeout:moveP@8
      L.LD(L.local_MR['seq_step[52]']['name'], L.local_MR['seq_step[52]']['addr'])
      L.TMS(L.local_T['block_timeout[52]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[52]']['name'], L.local_T['block_timeout[52]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+52, message='moveP@8:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+52, error_yaml=error_yaml)
      #;error:moveP@8
      L.LD(L.local_MR['seq_step[52]']['name'], L.local_MR['seq_step[52]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+52, message=f"moveP@8:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+52, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+52, message='moveP@8:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+52, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+52, message='moveP@8:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+52, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@8
      L.LDP(L.local_MR['seq_step[52]']['name'], L.local_MR['seq_step[52]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(-734.356, -173.218, 239.7, -178.932, 2.789, -132.003, 100.0, 100.0, 100.0, 5.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, override)
        RAC.send_command(f'moveAbsolutePtp({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')
      L.LD(L.local_MR['seq_step[52]']['name'], L.local_MR['seq_step[52]']['addr'])
      L.ANB(L.local_MR['seq_step[2052]']['name'], L.local_MR['seq_step[2052]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')
      L.LD(L.local_MR['seq_step[52]']['name'], L.local_MR['seq_step[52]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[52]']['addr'], 0.0)

      #;Process:moveP@9
      L.LD(L.local_MR['seq_step[2052]']['name'], L.local_MR['seq_step[2052]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2053]']['name'], L.local_MR['seq_step[2053]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[53]']['name'], L.local_MR['seq_step[53]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[53]']['name'], L.local_T['move_static_timer[53]']['addr'])
      L.ANPB(L.local_MR['seq_step[53]']['name'], L.local_MR['seq_step[53]']['addr'])
      L.OR(L.local_MR['seq_step[2053]']['name'], L.local_MR['seq_step[2053]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2053]']['name'], L.local_MR['seq_step[2053]']['addr'])
      #;Post-Process:moveP@9
      #;timeout:moveP@9
      L.LD(L.local_MR['seq_step[53]']['name'], L.local_MR['seq_step[53]']['addr'])
      L.TMS(L.local_T['block_timeout[53]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[53]']['name'], L.local_T['block_timeout[53]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+53, message='moveP@9:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+53, error_yaml=error_yaml)
      #;error:moveP@9
      L.LD(L.local_MR['seq_step[53]']['name'], L.local_MR['seq_step[53]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+53, message=f"moveP@9:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+53, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((10.0 == 0) or (10.0 == 0) or (10.0 == 0)):
          drive.register_error(no=801+53, message='moveP@9:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+53, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+53, message='moveP@9:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+53, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@9
      L.LDP(L.local_MR['seq_step[53]']['name'], L.local_MR['seq_step[53]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(-730.419, -175.589, 182.897, -179.718, 0.899, -131.968, 10.0, 10.0, 10.0, 0.2, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, override)
        RAC.send_command(f'moveAbsolutePtp({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')
      L.LD(L.local_MR['seq_step[53]']['name'], L.local_MR['seq_step[53]']['addr'])
      L.ANB(L.local_MR['seq_step[2053]']['name'], L.local_MR['seq_step[2053]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')
      L.LD(L.local_MR['seq_step[53]']['name'], L.local_MR['seq_step[53]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[53]']['addr'], 0.0)

      #;Process:procedures_callnoreturn@3
      L.LD(L.local_MR['seq_step[2053]']['name'], L.local_MR['seq_step[2053]']['addr'])
      L.MPS()
      L.LDB(L.local_MR['seq_step[2054]']['name'], L.local_MR['seq_step[2054]']['addr'])
      L.ANB(L.local_MR['seq_step[2045]']['name'], L.local_MR['seq_step[2045]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[54]']['name'], L.local_MR['seq_step[54]']['addr'])
      L.MPP()
      L.LD(L.local_MR['seq_step[2045]']['name'], L.local_MR['seq_step[2045]']['addr'])
      L.ANPB(L.local_MR['seq_step[54]']['name'], L.local_MR['seq_step[54]']['addr'])
      L.OR(L.local_MR['seq_step[2054]']['name'], L.local_MR['seq_step[2054]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2054]']['name'], L.local_MR['seq_step[2054]']['addr'])
      #;Post-Process:procedures_callnoreturn@3

      #;Process:wait_timer@4
      L.LD(L.local_MR['seq_step[2054]']['name'], L.local_MR['seq_step[2054]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2055]']['name'], L.local_MR['seq_step[2055]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[55]']['name'], L.local_MR['seq_step[55]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(L.local_T['block_timer1[55]']['name'], L.local_T['block_timer1[55]']['addr'])
      L.OR(L.local_MR['seq_step[2055]']['name'], L.local_MR['seq_step[2055]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2055]']['name'], L.local_MR['seq_step[2055]']['addr'])
      #;Post-Process:wait_timer@4
      #;timeout:wait_timer@4
      L.LD(L.local_MR['seq_step[55]']['name'], L.local_MR['seq_step[55]']['addr'])
      L.TMS(L.local_T['block_timeout[55]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[55]']['name'], L.local_T['block_timeout[55]']['addr'])
      if (L.aax & L.iix):
        drive.register_error(no=801+55, message='wait_timer@4:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+55, error_yaml=error_yaml)
      #;action:wait_timer@4
      L.LD(L.local_MR['seq_step[55]']['name'], L.local_MR['seq_step[55]']['addr'])
      L.TMS(L.local_T['block_timer1[55]']['addr'], wait_msec=number_param_yaml['N483']['value'])

      #;Process:moveP@19
      L.LD(L.local_MR['seq_step[2055]']['name'], L.local_MR['seq_step[2055]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2056]']['name'], L.local_MR['seq_step[2056]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[56]']['name'], L.local_MR['seq_step[56]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[56]']['name'], L.local_T['move_static_timer[56]']['addr'])
      L.ANPB(L.local_MR['seq_step[56]']['name'], L.local_MR['seq_step[56]']['addr'])
      L.OR(L.local_MR['seq_step[2056]']['name'], L.local_MR['seq_step[2056]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2056]']['name'], L.local_MR['seq_step[2056]']['addr'])
      #;Post-Process:moveP@19
      #;timeout:moveP@19
      L.LD(L.local_MR['seq_step[56]']['name'], L.local_MR['seq_step[56]']['addr'])
      L.TMS(L.local_T['block_timeout[56]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[56]']['name'], L.local_T['block_timeout[56]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+56, message='moveP@19:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+56, error_yaml=error_yaml)
      #;error:moveP@19
      L.LD(L.local_MR['seq_step[56]']['name'], L.local_MR['seq_step[56]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+56, message=f"moveP@19:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+56, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((10.0 == 0) or (10.0 == 0) or (10.0 == 0)):
          drive.register_error(no=801+56, message='moveP@19:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+56, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+56, message='moveP@19:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+56, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@19
      L.LDP(L.local_MR['seq_step[56]']['name'], L.local_MR['seq_step[56]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(-734.355, -173.221, 239.704, -178.933, 2.789, -132.003, 10.0, 10.0, 10.0, 5.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, override)
        RAC.send_command(f'moveAbsolutePtp({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')
      L.LD(L.local_MR['seq_step[56]']['name'], L.local_MR['seq_step[56]']['addr'])
      L.ANB(L.local_MR['seq_step[2056]']['name'], L.local_MR['seq_step[2056]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')
      L.LD(L.local_MR['seq_step[56]']['name'], L.local_MR['seq_step[56]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[56]']['addr'], 0.0)

      #;Process:moveP@10
      L.LD(L.local_MR['seq_step[2056]']['name'], L.local_MR['seq_step[2056]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2057]']['name'], L.local_MR['seq_step[2057]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[57]']['name'], L.local_MR['seq_step[57]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[57]']['name'], L.local_T['move_static_timer[57]']['addr'])
      L.ANPB(L.local_MR['seq_step[57]']['name'], L.local_MR['seq_step[57]']['addr'])
      L.OR(L.local_MR['seq_step[2057]']['name'], L.local_MR['seq_step[2057]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2057]']['name'], L.local_MR['seq_step[2057]']['addr'])
      #;Post-Process:moveP@10
      #;timeout:moveP@10
      L.LD(L.local_MR['seq_step[57]']['name'], L.local_MR['seq_step[57]']['addr'])
      L.TMS(L.local_T['block_timeout[57]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[57]']['name'], L.local_T['block_timeout[57]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+57, message='moveP@10:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+57, error_yaml=error_yaml)
      #;error:moveP@10
      L.LD(L.local_MR['seq_step[57]']['name'], L.local_MR['seq_step[57]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+57, message=f"moveP@10:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+57, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+57, message='moveP@10:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+57, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+57, message='moveP@10:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+57, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@10
      L.LDP(L.local_MR['seq_step[57]']['name'], L.local_MR['seq_step[57]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(-517.2, -165.2, 272.657, 179.809, 2.164, 46.48, 100.0, 100.0, 100.0, 5.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, override)
        RAC.send_command(f'moveAbsolutePtp({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')
      L.LD(L.local_MR['seq_step[57]']['name'], L.local_MR['seq_step[57]']['addr'])
      L.ANB(L.local_MR['seq_step[2057]']['name'], L.local_MR['seq_step[2057]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')
      L.LD(L.local_MR['seq_step[57]']['name'], L.local_MR['seq_step[57]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[57]']['addr'], 0.0)

      #;Process:moveP@11
      L.LD(L.local_MR['seq_step[2057]']['name'], L.local_MR['seq_step[2057]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2058]']['name'], L.local_MR['seq_step[2058]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[58]']['name'], L.local_MR['seq_step[58]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[58]']['name'], L.local_T['move_static_timer[58]']['addr'])
      L.ANPB(L.local_MR['seq_step[58]']['name'], L.local_MR['seq_step[58]']['addr'])
      L.OR(L.local_MR['seq_step[2058]']['name'], L.local_MR['seq_step[2058]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2058]']['name'], L.local_MR['seq_step[2058]']['addr'])
      #;Post-Process:moveP@11
      #;timeout:moveP@11
      L.LD(L.local_MR['seq_step[58]']['name'], L.local_MR['seq_step[58]']['addr'])
      L.TMS(L.local_T['block_timeout[58]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[58]']['name'], L.local_T['block_timeout[58]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+58, message='moveP@11:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+58, error_yaml=error_yaml)
      #;error:moveP@11
      L.LD(L.local_MR['seq_step[58]']['name'], L.local_MR['seq_step[58]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+58, message=f"moveP@11:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+58, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+58, message='moveP@11:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+58, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+58, message='moveP@11:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+58, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@11
      L.LDP(L.local_MR['seq_step[58]']['name'], L.local_MR['seq_step[58]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(-770.679, -172.126, 233.278, 178.914, 0.08, 45.758, 100.0, 100.0, 100.0, 5.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, override)
        RAC.send_command(f'moveAbsolutePtp({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')
      L.LD(L.local_MR['seq_step[58]']['name'], L.local_MR['seq_step[58]']['addr'])
      L.ANB(L.local_MR['seq_step[2058]']['name'], L.local_MR['seq_step[2058]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')
      L.LD(L.local_MR['seq_step[58]']['name'], L.local_MR['seq_step[58]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[58]']['addr'], 0.0)

      #;Process:moveP@12
      L.LD(L.local_MR['seq_step[2058]']['name'], L.local_MR['seq_step[2058]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2059]']['name'], L.local_MR['seq_step[2059]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[59]']['name'], L.local_MR['seq_step[59]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[59]']['name'], L.local_T['move_static_timer[59]']['addr'])
      L.ANPB(L.local_MR['seq_step[59]']['name'], L.local_MR['seq_step[59]']['addr'])
      L.OR(L.local_MR['seq_step[2059]']['name'], L.local_MR['seq_step[2059]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2059]']['name'], L.local_MR['seq_step[2059]']['addr'])
      #;Post-Process:moveP@12
      #;timeout:moveP@12
      L.LD(L.local_MR['seq_step[59]']['name'], L.local_MR['seq_step[59]']['addr'])
      L.TMS(L.local_T['block_timeout[59]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[59]']['name'], L.local_T['block_timeout[59]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+59, message='moveP@12:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+59, error_yaml=error_yaml)
      #;error:moveP@12
      L.LD(L.local_MR['seq_step[59]']['name'], L.local_MR['seq_step[59]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+59, message=f"moveP@12:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+59, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((10.0 == 0) or (10.0 == 0) or (10.0 == 0)):
          drive.register_error(no=801+59, message='moveP@12:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+59, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+59, message='moveP@12:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+59, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@12
      L.LDP(L.local_MR['seq_step[59]']['name'], L.local_MR['seq_step[59]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(-770.644, -172.112, 214.933, 178.905, 0.067, 45.761, 10.0, 10.0, 10.0, 0.2, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, override)
        RAC.send_command(f'moveAbsolutePtp({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')
      L.LD(L.local_MR['seq_step[59]']['name'], L.local_MR['seq_step[59]']['addr'])
      L.ANB(L.local_MR['seq_step[2059]']['name'], L.local_MR['seq_step[2059]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')
      L.LD(L.local_MR['seq_step[59]']['name'], L.local_MR['seq_step[59]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[59]']['addr'], 0.0)

      #;Process:procedures_callnoreturn@10
      L.LD(L.local_MR['seq_step[2059]']['name'], L.local_MR['seq_step[2059]']['addr'])
      L.MPS()
      L.LDB(L.local_MR['seq_step[2060]']['name'], L.local_MR['seq_step[2060]']['addr'])
      L.ANB(L.local_MR['seq_step[2068]']['name'], L.local_MR['seq_step[2068]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[60]']['name'], L.local_MR['seq_step[60]']['addr'])
      L.MPP()
      L.LD(L.local_MR['seq_step[2068]']['name'], L.local_MR['seq_step[2068]']['addr'])
      L.ANPB(L.local_MR['seq_step[60]']['name'], L.local_MR['seq_step[60]']['addr'])
      L.OR(L.local_MR['seq_step[2060]']['name'], L.local_MR['seq_step[2060]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2060]']['name'], L.local_MR['seq_step[2060]']['addr'])
      #;Post-Process:procedures_callnoreturn@10

      #;Process:wait_timer@14
      L.LD(L.local_MR['seq_step[2060]']['name'], L.local_MR['seq_step[2060]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2061]']['name'], L.local_MR['seq_step[2061]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[61]']['name'], L.local_MR['seq_step[61]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(L.local_T['block_timer1[61]']['name'], L.local_T['block_timer1[61]']['addr'])
      L.OR(L.local_MR['seq_step[2061]']['name'], L.local_MR['seq_step[2061]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2061]']['name'], L.local_MR['seq_step[2061]']['addr'])
      #;Post-Process:wait_timer@14
      #;timeout:wait_timer@14
      L.LD(L.local_MR['seq_step[61]']['name'], L.local_MR['seq_step[61]']['addr'])
      L.TMS(L.local_T['block_timeout[61]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[61]']['name'], L.local_T['block_timeout[61]']['addr'])
      if (L.aax & L.iix):
        drive.register_error(no=801+61, message='wait_timer@14:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+61, error_yaml=error_yaml)
      #;action:wait_timer@14
      L.LD(L.local_MR['seq_step[61]']['name'], L.local_MR['seq_step[61]']['addr'])
      L.TMS(L.local_T['block_timer1[61]']['addr'], wait_msec=number_param_yaml['N483']['value'])

      #;Process:moveP@13
      L.LD(L.local_MR['seq_step[2061]']['name'], L.local_MR['seq_step[2061]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2062]']['name'], L.local_MR['seq_step[2062]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[62]']['name'], L.local_MR['seq_step[62]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[62]']['name'], L.local_T['move_static_timer[62]']['addr'])
      L.ANPB(L.local_MR['seq_step[62]']['name'], L.local_MR['seq_step[62]']['addr'])
      L.OR(L.local_MR['seq_step[2062]']['name'], L.local_MR['seq_step[2062]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2062]']['name'], L.local_MR['seq_step[2062]']['addr'])
      #;Post-Process:moveP@13
      #;timeout:moveP@13
      L.LD(L.local_MR['seq_step[62]']['name'], L.local_MR['seq_step[62]']['addr'])
      L.TMS(L.local_T['block_timeout[62]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[62]']['name'], L.local_T['block_timeout[62]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+62, message='moveP@13:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+62, error_yaml=error_yaml)
      #;error:moveP@13
      L.LD(L.local_MR['seq_step[62]']['name'], L.local_MR['seq_step[62]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+62, message=f"moveP@13:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+62, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((10.0 == 0) or (10.0 == 0) or (10.0 == 0)):
          drive.register_error(no=801+62, message='moveP@13:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+62, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+62, message='moveP@13:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+62, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@13
      L.LDP(L.local_MR['seq_step[62]']['name'], L.local_MR['seq_step[62]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(-770.677, -172.126, 233.272, 178.914, 0.079, 45.759, 10.0, 10.0, 10.0, 5.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, override)
        RAC.send_command(f'moveAbsolutePtp({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')
      L.LD(L.local_MR['seq_step[62]']['name'], L.local_MR['seq_step[62]']['addr'])
      L.ANB(L.local_MR['seq_step[2062]']['name'], L.local_MR['seq_step[2062]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')
      L.LD(L.local_MR['seq_step[62]']['name'], L.local_MR['seq_step[62]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[62]']['addr'], 0.0)

      #;Process:moveP@22
      L.LD(L.local_MR['seq_step[2062]']['name'], L.local_MR['seq_step[2062]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2063]']['name'], L.local_MR['seq_step[2063]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[63]']['name'], L.local_MR['seq_step[63]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[63]']['name'], L.local_T['move_static_timer[63]']['addr'])
      L.ANPB(L.local_MR['seq_step[63]']['name'], L.local_MR['seq_step[63]']['addr'])
      L.OR(L.local_MR['seq_step[2063]']['name'], L.local_MR['seq_step[2063]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2063]']['name'], L.local_MR['seq_step[2063]']['addr'])
      #;Post-Process:moveP@22
      #;timeout:moveP@22
      L.LD(L.local_MR['seq_step[63]']['name'], L.local_MR['seq_step[63]']['addr'])
      L.TMS(L.local_T['block_timeout[63]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[63]']['name'], L.local_T['block_timeout[63]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+63, message='moveP@22:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+63, error_yaml=error_yaml)
      #;error:moveP@22
      L.LD(L.local_MR['seq_step[63]']['name'], L.local_MR['seq_step[63]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+63, message=f"moveP@22:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+63, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+63, message='moveP@22:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+63, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+63, message='moveP@22:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+63, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@22
      L.LDP(L.local_MR['seq_step[63]']['name'], L.local_MR['seq_step[63]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(-511.236, -163.017, 337.492, 177.37, -0.032, -134.999, 100.0, 100.0, 100.0, 5.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, override)
        RAC.send_command(f'moveAbsolutePtp({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')
      L.LD(L.local_MR['seq_step[63]']['name'], L.local_MR['seq_step[63]']['addr'])
      L.ANB(L.local_MR['seq_step[2063]']['name'], L.local_MR['seq_step[2063]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')
      L.LD(L.local_MR['seq_step[63]']['name'], L.local_MR['seq_step[63]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[63]']['addr'], 0.0)

      #;Process:moveP@23
      L.LD(L.local_MR['seq_step[2063]']['name'], L.local_MR['seq_step[2063]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2064]']['name'], L.local_MR['seq_step[2064]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[64]']['name'], L.local_MR['seq_step[64]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[64]']['name'], L.local_T['move_static_timer[64]']['addr'])
      L.ANPB(L.local_MR['seq_step[64]']['name'], L.local_MR['seq_step[64]']['addr'])
      L.OR(L.local_MR['seq_step[2064]']['name'], L.local_MR['seq_step[2064]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2064]']['name'], L.local_MR['seq_step[2064]']['addr'])
      #;Post-Process:moveP@23
      #;timeout:moveP@23
      L.LD(L.local_MR['seq_step[64]']['name'], L.local_MR['seq_step[64]']['addr'])
      L.TMS(L.local_T['block_timeout[64]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[64]']['name'], L.local_T['block_timeout[64]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+64, message='moveP@23:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+64, error_yaml=error_yaml)
      #;error:moveP@23
      L.LD(L.local_MR['seq_step[64]']['name'], L.local_MR['seq_step[64]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+64, message=f"moveP@23:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+64, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+64, message='moveP@23:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+64, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+64, message='moveP@23:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+64, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@23
      L.LDP(L.local_MR['seq_step[64]']['name'], L.local_MR['seq_step[64]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(-126.434, -280.319, 361.422, -178.908, 0.419, -46.383, 100.0, 100.0, 100.0, 5.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, override)
        RAC.send_command(f'moveAbsolutePtp({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')
      L.LD(L.local_MR['seq_step[64]']['name'], L.local_MR['seq_step[64]']['addr'])
      L.ANB(L.local_MR['seq_step[2064]']['name'], L.local_MR['seq_step[2064]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')
      L.LD(L.local_MR['seq_step[64]']['name'], L.local_MR['seq_step[64]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[64]']['addr'], 0.0)


      #;Process:procedures_defnoreturn@3
      L.LD(L.local_MR['seq_step[3]']['name'], L.local_MR['seq_step[3]']['addr'])
      L.OR(L.local_MR['seq_step[60]']['name'], L.local_MR['seq_step[60]']['addr'])
      L.OR(L.local_MR['seq_step[100]']['name'], L.local_MR['seq_step[100]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2065]']['name'], L.local_MR['seq_step[2065]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[65]']['name'], L.local_MR['seq_step[65]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.ANPB(L.local_MR['seq_step[65]']['name'], L.local_MR['seq_step[65]']['addr'])
      L.OR(L.local_MR['seq_step[2065]']['name'], L.local_MR['seq_step[2065]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2065]']['name'], L.local_MR['seq_step[2065]']['addr'])
      #;Post-Process:procedures_defnoreturn@3

      #;Process:wait_timer@12
      L.LD(L.local_MR['seq_step[2065]']['name'], L.local_MR['seq_step[2065]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2066]']['name'], L.local_MR['seq_step[2066]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[66]']['name'], L.local_MR['seq_step[66]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(L.local_T['block_timer1[66]']['name'], L.local_T['block_timer1[66]']['addr'])
      L.OR(L.local_MR['seq_step[2066]']['name'], L.local_MR['seq_step[2066]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2066]']['name'], L.local_MR['seq_step[2066]']['addr'])
      #;Post-Process:wait_timer@12
      #;timeout:wait_timer@12
      L.LD(L.local_MR['seq_step[66]']['name'], L.local_MR['seq_step[66]']['addr'])
      L.TMS(L.local_T['block_timeout[66]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[66]']['name'], L.local_T['block_timeout[66]']['addr'])
      if (L.aax & L.iix):
        drive.register_error(no=801+66, message='wait_timer@12:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+66, error_yaml=error_yaml)
      #;action:wait_timer@12
      L.LD(L.local_MR['seq_step[66]']['name'], L.local_MR['seq_step[66]']['addr'])
      L.TMS(L.local_T['block_timer1[66]']['addr'], wait_msec=number_param_yaml['N482']['value'])

      #;Process:set_output@3
      L.LD(L.local_MR['seq_step[2066]']['name'], L.local_MR['seq_step[2066]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2067]']['name'], L.local_MR['seq_step[2067]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[67]']['name'], L.local_MR['seq_step[67]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(L.local_MR['robot_io_success[0]']['name'], L.local_MR['robot_io_success[0]']['addr'])
      L.ANPB(L.local_MR['seq_step[67]']['name'], L.local_MR['seq_step[67]']['addr'])
      L.OR(L.local_MR['seq_step[2067]']['name'], L.local_MR['seq_step[2067]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2067]']['name'], L.local_MR['seq_step[2067]']['addr'])
      #;Post-Process:set_output@3
      #;timeout:set_output@3
      L.LD(L.local_MR['seq_step[67]']['name'], L.local_MR['seq_step[67]']['addr'])
      L.TMS(L.local_T['block_timeout[67]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[67]']['name'], L.local_T['block_timeout[67]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+67, message='set_output@3:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+67, error_yaml=error_yaml)
      L.LD(L.local_MR['seq_step[67]']['name'], L.local_MR['seq_step[67]']['addr'])
      L.ANB(L.local_MR['robot_io_success[0]']['name'], L.local_MR['robot_io_success[0]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        success = RAC.send_command('setOutputON(2)')
        if (success): L.setRelay(L.local_MR['robot_io_success[0]']['name'], L.local_MR['robot_io_success[0]']['addr'])
        else        : L.resetRelay(L.local_MR['robot_io_success[0]']['name'], L.local_MR['robot_io_success[0]']['addr'])
      L.LDP(L.local_MR['seq_step[2067]']['name'], L.local_MR['seq_step[2067]']['addr'])
      if (L.aax & L.iix):
        L.resetRelay(L.local_MR['robot_io_success[0]']['name'], L.local_MR['robot_io_success[0]']['addr'])

      #;Process:wait_input@1
      L.LD(L.local_MR['seq_step[2067]']['name'], L.local_MR['seq_step[2067]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2068]']['name'], L.local_MR['seq_step[2068]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[68]']['name'], L.local_MR['seq_step[68]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(True if robot_status['input_signal'][2] else False)
      L.ANPB(L.local_MR['seq_step[68]']['name'], L.local_MR['seq_step[68]']['addr'])
      L.OR(L.local_MR['seq_step[2068]']['name'], L.local_MR['seq_step[2068]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2068]']['name'], L.local_MR['seq_step[2068]']['addr'])
      #;timeout:wait_input@1
      L.LD(L.local_MR['seq_step[68]']['name'], L.local_MR['seq_step[68]']['addr'])
      L.TMS(L.local_T['block_timeout[68]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[68]']['name'], L.local_T['block_timeout[68]']['addr'])
      if (L.aax & L.iix):
        drive.register_error(no=801+68, message='wait_input@1:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+68, error_yaml=error_yaml)
      #;action:wait_input@1
      L.LD(L.local_MR['seq_step[68]']['name'], L.local_MR['seq_step[68]']['addr'])
      if (L.aax & L.iix):
        RAC.send_command('getInput(2)')


      #;Process:procedures_defnoreturn@4
      L.LD(L.local_MR['seq_step[5]']['name'], L.local_MR['seq_step[5]']['addr'])
      L.OR(L.local_MR['seq_step[93]']['name'], L.local_MR['seq_step[93]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2069]']['name'], L.local_MR['seq_step[2069]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[69]']['name'], L.local_MR['seq_step[69]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.ANPB(L.local_MR['seq_step[69]']['name'], L.local_MR['seq_step[69]']['addr'])
      L.OR(L.local_MR['seq_step[2069]']['name'], L.local_MR['seq_step[2069]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2069]']['name'], L.local_MR['seq_step[2069]']['addr'])
      #;Post-Process:procedures_defnoreturn@4

      #;Process:wait_timer@13
      L.LD(L.local_MR['seq_step[2069]']['name'], L.local_MR['seq_step[2069]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2070]']['name'], L.local_MR['seq_step[2070]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[70]']['name'], L.local_MR['seq_step[70]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(L.local_T['block_timer1[70]']['name'], L.local_T['block_timer1[70]']['addr'])
      L.OR(L.local_MR['seq_step[2070]']['name'], L.local_MR['seq_step[2070]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2070]']['name'], L.local_MR['seq_step[2070]']['addr'])
      #;Post-Process:wait_timer@13
      #;timeout:wait_timer@13
      L.LD(L.local_MR['seq_step[70]']['name'], L.local_MR['seq_step[70]']['addr'])
      L.TMS(L.local_T['block_timeout[70]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[70]']['name'], L.local_T['block_timeout[70]']['addr'])
      if (L.aax & L.iix):
        drive.register_error(no=801+70, message='wait_timer@13:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+70, error_yaml=error_yaml)
      #;action:wait_timer@13
      L.LD(L.local_MR['seq_step[70]']['name'], L.local_MR['seq_step[70]']['addr'])
      L.TMS(L.local_T['block_timer1[70]']['addr'], wait_msec=number_param_yaml['N482']['value'])

      #;Process:set_output@4
      L.LD(L.local_MR['seq_step[2070]']['name'], L.local_MR['seq_step[2070]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2071]']['name'], L.local_MR['seq_step[2071]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[71]']['name'], L.local_MR['seq_step[71]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(L.local_MR['robot_io_success[0]']['name'], L.local_MR['robot_io_success[0]']['addr'])
      L.ANPB(L.local_MR['seq_step[71]']['name'], L.local_MR['seq_step[71]']['addr'])
      L.OR(L.local_MR['seq_step[2071]']['name'], L.local_MR['seq_step[2071]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2071]']['name'], L.local_MR['seq_step[2071]']['addr'])
      #;Post-Process:set_output@4
      #;timeout:set_output@4
      L.LD(L.local_MR['seq_step[71]']['name'], L.local_MR['seq_step[71]']['addr'])
      L.TMS(L.local_T['block_timeout[71]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[71]']['name'], L.local_T['block_timeout[71]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+71, message='set_output@4:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+71, error_yaml=error_yaml)
      L.LD(L.local_MR['seq_step[71]']['name'], L.local_MR['seq_step[71]']['addr'])
      L.ANB(L.local_MR['robot_io_success[0]']['name'], L.local_MR['robot_io_success[0]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        success = RAC.send_command('setOutputOFF(2)')
        if (success): L.setRelay(L.local_MR['robot_io_success[0]']['name'], L.local_MR['robot_io_success[0]']['addr'])
        else        : L.resetRelay(L.local_MR['robot_io_success[0]']['name'], L.local_MR['robot_io_success[0]']['addr'])
      L.LDP(L.local_MR['seq_step[2071]']['name'], L.local_MR['seq_step[2071]']['addr'])
      if (L.aax & L.iix):
        L.resetRelay(L.local_MR['robot_io_success[0]']['name'], L.local_MR['robot_io_success[0]']['addr'])

      #;Process:wait_input@4
      L.LD(L.local_MR['seq_step[2071]']['name'], L.local_MR['seq_step[2071]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2072]']['name'], L.local_MR['seq_step[2072]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[72]']['name'], L.local_MR['seq_step[72]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(True if robot_status['input_signal'][3] else False)
      L.ANPB(L.local_MR['seq_step[72]']['name'], L.local_MR['seq_step[72]']['addr'])
      L.OR(L.local_MR['seq_step[2072]']['name'], L.local_MR['seq_step[2072]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2072]']['name'], L.local_MR['seq_step[2072]']['addr'])
      #;timeout:wait_input@4
      L.LD(L.local_MR['seq_step[72]']['name'], L.local_MR['seq_step[72]']['addr'])
      L.TMS(L.local_T['block_timeout[72]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[72]']['name'], L.local_T['block_timeout[72]']['addr'])
      if (L.aax & L.iix):
        drive.register_error(no=801+72, message='wait_input@4:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+72, error_yaml=error_yaml)
      #;action:wait_input@4
      L.LD(L.local_MR['seq_step[72]']['name'], L.local_MR['seq_step[72]']['addr'])
      if (L.aax & L.iix):
        RAC.send_command('getInput(3)')


      #;Process:procedures_defnoreturn@8
      L.LD(L.local_MR['seq_step[24]']['name'], L.local_MR['seq_step[24]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2073]']['name'], L.local_MR['seq_step[2073]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[73]']['name'], L.local_MR['seq_step[73]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.ANPB(L.local_MR['seq_step[73]']['name'], L.local_MR['seq_step[73]']['addr'])
      L.OR(L.local_MR['seq_step[2073]']['name'], L.local_MR['seq_step[2073]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2073]']['name'], L.local_MR['seq_step[2073]']['addr'])
      #;Post-Process:procedures_defnoreturn@8

      #;Process:moveP@54
      L.LD(L.local_MR['seq_step[2073]']['name'], L.local_MR['seq_step[2073]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2074]']['name'], L.local_MR['seq_step[2074]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[74]']['name'], L.local_MR['seq_step[74]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[74]']['name'], L.local_T['move_static_timer[74]']['addr'])
      L.ANPB(L.local_MR['seq_step[74]']['name'], L.local_MR['seq_step[74]']['addr'])
      L.OR(L.local_MR['seq_step[2074]']['name'], L.local_MR['seq_step[2074]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2074]']['name'], L.local_MR['seq_step[2074]']['addr'])
      #;Post-Process:moveP@54
      #;timeout:moveP@54
      L.LD(L.local_MR['seq_step[74]']['name'], L.local_MR['seq_step[74]']['addr'])
      L.TMS(L.local_T['block_timeout[74]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[74]']['name'], L.local_T['block_timeout[74]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+74, message='moveP@54:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+74, error_yaml=error_yaml)
      #;error:moveP@54
      L.LD(L.local_MR['seq_step[74]']['name'], L.local_MR['seq_step[74]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+74, message=f"moveP@54:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+74, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+74, message='moveP@54:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+74, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+74, message='moveP@54:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+74, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@54
      L.LDP(L.local_MR['seq_step[74]']['name'], L.local_MR['seq_step[74]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(-126.434, -280.319, 361.422, -178.908, 0.419, -46.383, 100.0, 100.0, 100.0, 5.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, override)
        RAC.send_command(f'moveAbsolutePtp({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')
      L.LD(L.local_MR['seq_step[74]']['name'], L.local_MR['seq_step[74]']['addr'])
      L.ANB(L.local_MR['seq_step[2074]']['name'], L.local_MR['seq_step[2074]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')
      L.LD(L.local_MR['seq_step[74]']['name'], L.local_MR['seq_step[74]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[74]']['addr'], 0.0)

      #;Process:moveP@24
      L.LD(L.local_MR['seq_step[2074]']['name'], L.local_MR['seq_step[2074]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2075]']['name'], L.local_MR['seq_step[2075]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[75]']['name'], L.local_MR['seq_step[75]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[75]']['name'], L.local_T['move_static_timer[75]']['addr'])
      L.ANPB(L.local_MR['seq_step[75]']['name'], L.local_MR['seq_step[75]']['addr'])
      L.OR(L.local_MR['seq_step[2075]']['name'], L.local_MR['seq_step[2075]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2075]']['name'], L.local_MR['seq_step[2075]']['addr'])
      #;Post-Process:moveP@24
      #;timeout:moveP@24
      L.LD(L.local_MR['seq_step[75]']['name'], L.local_MR['seq_step[75]']['addr'])
      L.TMS(L.local_T['block_timeout[75]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[75]']['name'], L.local_T['block_timeout[75]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+75, message='moveP@24:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+75, error_yaml=error_yaml)
      #;error:moveP@24
      L.LD(L.local_MR['seq_step[75]']['name'], L.local_MR['seq_step[75]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+75, message=f"moveP@24:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+75, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+75, message='moveP@24:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+75, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+75, message='moveP@24:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+75, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@24
      L.LDP(L.local_MR['seq_step[75]']['name'], L.local_MR['seq_step[75]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(-734.356, -173.218, 239.7, -178.932, 2.789, -132.003, 100.0, 100.0, 100.0, 5.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, override)
        RAC.send_command(f'moveAbsolutePtp({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')
      L.LD(L.local_MR['seq_step[75]']['name'], L.local_MR['seq_step[75]']['addr'])
      L.ANB(L.local_MR['seq_step[2075]']['name'], L.local_MR['seq_step[2075]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')
      L.LD(L.local_MR['seq_step[75]']['name'], L.local_MR['seq_step[75]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[75]']['addr'], 0.0)

      #;Process:moveP@25
      L.LD(L.local_MR['seq_step[2075]']['name'], L.local_MR['seq_step[2075]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2076]']['name'], L.local_MR['seq_step[2076]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[76]']['name'], L.local_MR['seq_step[76]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[76]']['name'], L.local_T['move_static_timer[76]']['addr'])
      L.ANPB(L.local_MR['seq_step[76]']['name'], L.local_MR['seq_step[76]']['addr'])
      L.OR(L.local_MR['seq_step[2076]']['name'], L.local_MR['seq_step[2076]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2076]']['name'], L.local_MR['seq_step[2076]']['addr'])
      #;Post-Process:moveP@25
      #;timeout:moveP@25
      L.LD(L.local_MR['seq_step[76]']['name'], L.local_MR['seq_step[76]']['addr'])
      L.TMS(L.local_T['block_timeout[76]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[76]']['name'], L.local_T['block_timeout[76]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+76, message='moveP@25:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+76, error_yaml=error_yaml)
      #;error:moveP@25
      L.LD(L.local_MR['seq_step[76]']['name'], L.local_MR['seq_step[76]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+76, message=f"moveP@25:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+76, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((10.0 == 0) or (10.0 == 0) or (10.0 == 0)):
          drive.register_error(no=801+76, message='moveP@25:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+76, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+76, message='moveP@25:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+76, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@25
      L.LDP(L.local_MR['seq_step[76]']['name'], L.local_MR['seq_step[76]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(-730.419, -175.589, 182.897, -179.718, 0.899, -131.968, 10.0, 10.0, 10.0, 0.2, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, override)
        RAC.send_command(f'moveAbsolutePtp({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')
      L.LD(L.local_MR['seq_step[76]']['name'], L.local_MR['seq_step[76]']['addr'])
      L.ANB(L.local_MR['seq_step[2076]']['name'], L.local_MR['seq_step[2076]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')
      L.LD(L.local_MR['seq_step[76]']['name'], L.local_MR['seq_step[76]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[76]']['addr'], 0.0)

      #;Process:procedures_callnoreturn@4
      L.LD(L.local_MR['seq_step[2076]']['name'], L.local_MR['seq_step[2076]']['addr'])
      L.MPS()
      L.LDB(L.local_MR['seq_step[2077]']['name'], L.local_MR['seq_step[2077]']['addr'])
      L.ANB(L.local_MR['seq_step[2049]']['name'], L.local_MR['seq_step[2049]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[77]']['name'], L.local_MR['seq_step[77]']['addr'])
      L.MPP()
      L.LD(L.local_MR['seq_step[2049]']['name'], L.local_MR['seq_step[2049]']['addr'])
      L.ANPB(L.local_MR['seq_step[77]']['name'], L.local_MR['seq_step[77]']['addr'])
      L.OR(L.local_MR['seq_step[2077]']['name'], L.local_MR['seq_step[2077]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2077]']['name'], L.local_MR['seq_step[2077]']['addr'])
      #;Post-Process:procedures_callnoreturn@4

      #;Process:wait_timer@11
      L.LD(L.local_MR['seq_step[2077]']['name'], L.local_MR['seq_step[2077]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2078]']['name'], L.local_MR['seq_step[2078]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[78]']['name'], L.local_MR['seq_step[78]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(L.local_T['block_timer1[78]']['name'], L.local_T['block_timer1[78]']['addr'])
      L.OR(L.local_MR['seq_step[2078]']['name'], L.local_MR['seq_step[2078]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2078]']['name'], L.local_MR['seq_step[2078]']['addr'])
      #;Post-Process:wait_timer@11
      #;timeout:wait_timer@11
      L.LD(L.local_MR['seq_step[78]']['name'], L.local_MR['seq_step[78]']['addr'])
      L.TMS(L.local_T['block_timeout[78]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[78]']['name'], L.local_T['block_timeout[78]']['addr'])
      if (L.aax & L.iix):
        drive.register_error(no=801+78, message='wait_timer@11:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+78, error_yaml=error_yaml)
      #;action:wait_timer@11
      L.LD(L.local_MR['seq_step[78]']['name'], L.local_MR['seq_step[78]']['addr'])
      L.TMS(L.local_T['block_timer1[78]']['addr'], wait_msec=number_param_yaml['N483']['value'])

      #;Process:moveP@26
      L.LD(L.local_MR['seq_step[2078]']['name'], L.local_MR['seq_step[2078]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2079]']['name'], L.local_MR['seq_step[2079]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[79]']['name'], L.local_MR['seq_step[79]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[79]']['name'], L.local_T['move_static_timer[79]']['addr'])
      L.ANPB(L.local_MR['seq_step[79]']['name'], L.local_MR['seq_step[79]']['addr'])
      L.OR(L.local_MR['seq_step[2079]']['name'], L.local_MR['seq_step[2079]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2079]']['name'], L.local_MR['seq_step[2079]']['addr'])
      #;Post-Process:moveP@26
      #;timeout:moveP@26
      L.LD(L.local_MR['seq_step[79]']['name'], L.local_MR['seq_step[79]']['addr'])
      L.TMS(L.local_T['block_timeout[79]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[79]']['name'], L.local_T['block_timeout[79]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+79, message='moveP@26:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+79, error_yaml=error_yaml)
      #;error:moveP@26
      L.LD(L.local_MR['seq_step[79]']['name'], L.local_MR['seq_step[79]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+79, message=f"moveP@26:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+79, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+79, message='moveP@26:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+79, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+79, message='moveP@26:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+79, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@26
      L.LDP(L.local_MR['seq_step[79]']['name'], L.local_MR['seq_step[79]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(-734.356, -173.218, 239.7, -178.932, 2.789, -132.003, 100.0, 100.0, 100.0, 5.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, override)
        RAC.send_command(f'moveAbsolutePtp({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')
      L.LD(L.local_MR['seq_step[79]']['name'], L.local_MR['seq_step[79]']['addr'])
      L.ANB(L.local_MR['seq_step[2079]']['name'], L.local_MR['seq_step[2079]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')
      L.LD(L.local_MR['seq_step[79]']['name'], L.local_MR['seq_step[79]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[79]']['addr'], 0.0)

      #;Process:moveP@27
      L.LD(L.local_MR['seq_step[2079]']['name'], L.local_MR['seq_step[2079]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2080]']['name'], L.local_MR['seq_step[2080]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[80]']['name'], L.local_MR['seq_step[80]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[80]']['name'], L.local_T['move_static_timer[80]']['addr'])
      L.ANPB(L.local_MR['seq_step[80]']['name'], L.local_MR['seq_step[80]']['addr'])
      L.OR(L.local_MR['seq_step[2080]']['name'], L.local_MR['seq_step[2080]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2080]']['name'], L.local_MR['seq_step[2080]']['addr'])
      #;Post-Process:moveP@27
      #;timeout:moveP@27
      L.LD(L.local_MR['seq_step[80]']['name'], L.local_MR['seq_step[80]']['addr'])
      L.TMS(L.local_T['block_timeout[80]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[80]']['name'], L.local_T['block_timeout[80]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+80, message='moveP@27:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+80, error_yaml=error_yaml)
      #;error:moveP@27
      L.LD(L.local_MR['seq_step[80]']['name'], L.local_MR['seq_step[80]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+80, message=f"moveP@27:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+80, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+80, message='moveP@27:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+80, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+80, message='moveP@27:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+80, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@27
      L.LDP(L.local_MR['seq_step[80]']['name'], L.local_MR['seq_step[80]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(-126.434, -280.319, 361.422, -178.908, 0.419, -46.383, 100.0, 100.0, 100.0, 5.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, override)
        RAC.send_command(f'moveAbsolutePtp({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')
      L.LD(L.local_MR['seq_step[80]']['name'], L.local_MR['seq_step[80]']['addr'])
      L.ANB(L.local_MR['seq_step[2080]']['name'], L.local_MR['seq_step[2080]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')
      L.LD(L.local_MR['seq_step[80]']['name'], L.local_MR['seq_step[80]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[80]']['addr'], 0.0)


      #;Process:procedures_defnoreturn@9
      L.LD(L.local_MR['seq_step[26]']['name'], L.local_MR['seq_step[26]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2081]']['name'], L.local_MR['seq_step[2081]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[81]']['name'], L.local_MR['seq_step[81]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.ANPB(L.local_MR['seq_step[81]']['name'], L.local_MR['seq_step[81]']['addr'])
      L.OR(L.local_MR['seq_step[2081]']['name'], L.local_MR['seq_step[2081]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2081]']['name'], L.local_MR['seq_step[2081]']['addr'])
      #;Post-Process:procedures_defnoreturn@9

      #;Process:moveP@29
      L.LD(L.local_MR['seq_step[2081]']['name'], L.local_MR['seq_step[2081]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2082]']['name'], L.local_MR['seq_step[2082]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[82]']['name'], L.local_MR['seq_step[82]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[82]']['name'], L.local_T['move_static_timer[82]']['addr'])
      L.ANPB(L.local_MR['seq_step[82]']['name'], L.local_MR['seq_step[82]']['addr'])
      L.OR(L.local_MR['seq_step[2082]']['name'], L.local_MR['seq_step[2082]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2082]']['name'], L.local_MR['seq_step[2082]']['addr'])
      #;Post-Process:moveP@29
      #;timeout:moveP@29
      L.LD(L.local_MR['seq_step[82]']['name'], L.local_MR['seq_step[82]']['addr'])
      L.TMS(L.local_T['block_timeout[82]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[82]']['name'], L.local_T['block_timeout[82]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+82, message='moveP@29:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+82, error_yaml=error_yaml)
      #;error:moveP@29
      L.LD(L.local_MR['seq_step[82]']['name'], L.local_MR['seq_step[82]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+82, message=f"moveP@29:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+82, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+82, message='moveP@29:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+82, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+82, message='moveP@29:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+82, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@29
      L.LDP(L.local_MR['seq_step[82]']['name'], L.local_MR['seq_step[82]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(98.001, -447.154, 283.73, 177.598, 2.269, -46.0, 100.0, 100.0, 100.0, 5.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, override)
        RAC.send_command(f'moveAbsolutePtp({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')
      L.LD(L.local_MR['seq_step[82]']['name'], L.local_MR['seq_step[82]']['addr'])
      L.ANB(L.local_MR['seq_step[2082]']['name'], L.local_MR['seq_step[2082]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')
      L.LD(L.local_MR['seq_step[82]']['name'], L.local_MR['seq_step[82]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[82]']['addr'], 0.0)

      #;Process:moveP@30
      L.LD(L.local_MR['seq_step[2082]']['name'], L.local_MR['seq_step[2082]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2083]']['name'], L.local_MR['seq_step[2083]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[83]']['name'], L.local_MR['seq_step[83]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[83]']['name'], L.local_T['move_static_timer[83]']['addr'])
      L.ANPB(L.local_MR['seq_step[83]']['name'], L.local_MR['seq_step[83]']['addr'])
      L.OR(L.local_MR['seq_step[2083]']['name'], L.local_MR['seq_step[2083]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2083]']['name'], L.local_MR['seq_step[2083]']['addr'])
      #;Post-Process:moveP@30
      #;timeout:moveP@30
      L.LD(L.local_MR['seq_step[83]']['name'], L.local_MR['seq_step[83]']['addr'])
      L.TMS(L.local_T['block_timeout[83]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[83]']['name'], L.local_T['block_timeout[83]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+83, message='moveP@30:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+83, error_yaml=error_yaml)
      #;error:moveP@30
      L.LD(L.local_MR['seq_step[83]']['name'], L.local_MR['seq_step[83]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+83, message=f"moveP@30:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+83, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+83, message='moveP@30:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+83, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+83, message='moveP@30:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+83, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@30
      L.LDP(L.local_MR['seq_step[83]']['name'], L.local_MR['seq_step[83]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(97.996, -879.312, 169.168, 177.598, 2.27, -46.001, 100.0, 100.0, 100.0, 5.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, override)
        RAC.send_command(f'moveAbsolutePtp({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')
      L.LD(L.local_MR['seq_step[83]']['name'], L.local_MR['seq_step[83]']['addr'])
      L.ANB(L.local_MR['seq_step[2083]']['name'], L.local_MR['seq_step[2083]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')
      L.LD(L.local_MR['seq_step[83]']['name'], L.local_MR['seq_step[83]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[83]']['addr'], 0.0)

      #;Process:moveP@31
      L.LD(L.local_MR['seq_step[2083]']['name'], L.local_MR['seq_step[2083]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2084]']['name'], L.local_MR['seq_step[2084]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[84]']['name'], L.local_MR['seq_step[84]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[84]']['name'], L.local_T['move_static_timer[84]']['addr'])
      L.ANPB(L.local_MR['seq_step[84]']['name'], L.local_MR['seq_step[84]']['addr'])
      L.OR(L.local_MR['seq_step[2084]']['name'], L.local_MR['seq_step[2084]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2084]']['name'], L.local_MR['seq_step[2084]']['addr'])
      #;Post-Process:moveP@31
      #;timeout:moveP@31
      L.LD(L.local_MR['seq_step[84]']['name'], L.local_MR['seq_step[84]']['addr'])
      L.TMS(L.local_T['block_timeout[84]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[84]']['name'], L.local_T['block_timeout[84]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+84, message='moveP@31:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+84, error_yaml=error_yaml)
      #;error:moveP@31
      L.LD(L.local_MR['seq_step[84]']['name'], L.local_MR['seq_step[84]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+84, message=f"moveP@31:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+84, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+84, message='moveP@31:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+84, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+84, message='moveP@31:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+84, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@31
      L.LDP(L.local_MR['seq_step[84]']['name'], L.local_MR['seq_step[84]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(97.999, -879.311, 111.098, 177.599, 2.27, -46.001, 100.0, 100.0, 100.0, 0.2, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, override)
        RAC.send_command(f'moveAbsolutePtp({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')
      L.LD(L.local_MR['seq_step[84]']['name'], L.local_MR['seq_step[84]']['addr'])
      L.ANB(L.local_MR['seq_step[2084]']['name'], L.local_MR['seq_step[2084]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')
      L.LD(L.local_MR['seq_step[84]']['name'], L.local_MR['seq_step[84]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[84]']['addr'], 0.0)

      #;Process:procedures_callnoreturn@5
      L.LD(L.local_MR['seq_step[2084]']['name'], L.local_MR['seq_step[2084]']['addr'])
      L.MPS()
      L.LDB(L.local_MR['seq_step[2085]']['name'], L.local_MR['seq_step[2085]']['addr'])
      L.ANB(L.local_MR['seq_step[2045]']['name'], L.local_MR['seq_step[2045]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[85]']['name'], L.local_MR['seq_step[85]']['addr'])
      L.MPP()
      L.LD(L.local_MR['seq_step[2045]']['name'], L.local_MR['seq_step[2045]']['addr'])
      L.ANPB(L.local_MR['seq_step[85]']['name'], L.local_MR['seq_step[85]']['addr'])
      L.OR(L.local_MR['seq_step[2085]']['name'], L.local_MR['seq_step[2085]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2085]']['name'], L.local_MR['seq_step[2085]']['addr'])
      #;Post-Process:procedures_callnoreturn@5

      #;Process:wait_timer@7
      L.LD(L.local_MR['seq_step[2085]']['name'], L.local_MR['seq_step[2085]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2086]']['name'], L.local_MR['seq_step[2086]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[86]']['name'], L.local_MR['seq_step[86]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(L.local_T['block_timer1[86]']['name'], L.local_T['block_timer1[86]']['addr'])
      L.OR(L.local_MR['seq_step[2086]']['name'], L.local_MR['seq_step[2086]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2086]']['name'], L.local_MR['seq_step[2086]']['addr'])
      #;Post-Process:wait_timer@7
      #;timeout:wait_timer@7
      L.LD(L.local_MR['seq_step[86]']['name'], L.local_MR['seq_step[86]']['addr'])
      L.TMS(L.local_T['block_timeout[86]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[86]']['name'], L.local_T['block_timeout[86]']['addr'])
      if (L.aax & L.iix):
        drive.register_error(no=801+86, message='wait_timer@7:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+86, error_yaml=error_yaml)
      #;action:wait_timer@7
      L.LD(L.local_MR['seq_step[86]']['name'], L.local_MR['seq_step[86]']['addr'])
      L.TMS(L.local_T['block_timer1[86]']['addr'], wait_msec=number_param_yaml['N483']['value'])

      #;Process:moveP@32
      L.LD(L.local_MR['seq_step[2086]']['name'], L.local_MR['seq_step[2086]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2087]']['name'], L.local_MR['seq_step[2087]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[87]']['name'], L.local_MR['seq_step[87]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[87]']['name'], L.local_T['move_static_timer[87]']['addr'])
      L.ANPB(L.local_MR['seq_step[87]']['name'], L.local_MR['seq_step[87]']['addr'])
      L.OR(L.local_MR['seq_step[2087]']['name'], L.local_MR['seq_step[2087]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2087]']['name'], L.local_MR['seq_step[2087]']['addr'])
      #;Post-Process:moveP@32
      #;timeout:moveP@32
      L.LD(L.local_MR['seq_step[87]']['name'], L.local_MR['seq_step[87]']['addr'])
      L.TMS(L.local_T['block_timeout[87]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[87]']['name'], L.local_T['block_timeout[87]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+87, message='moveP@32:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+87, error_yaml=error_yaml)
      #;error:moveP@32
      L.LD(L.local_MR['seq_step[87]']['name'], L.local_MR['seq_step[87]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+87, message=f"moveP@32:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+87, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+87, message='moveP@32:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+87, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+87, message='moveP@32:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+87, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@32
      L.LDP(L.local_MR['seq_step[87]']['name'], L.local_MR['seq_step[87]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(97.996, -879.312, 169.168, 177.598, 2.27, -46.001, 100.0, 100.0, 100.0, 5.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, override)
        RAC.send_command(f'moveAbsolutePtp({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')
      L.LD(L.local_MR['seq_step[87]']['name'], L.local_MR['seq_step[87]']['addr'])
      L.ANB(L.local_MR['seq_step[2087]']['name'], L.local_MR['seq_step[2087]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')
      L.LD(L.local_MR['seq_step[87]']['name'], L.local_MR['seq_step[87]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[87]']['addr'], 0.0)

      #;Process:moveP@33
      L.LD(L.local_MR['seq_step[2087]']['name'], L.local_MR['seq_step[2087]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2088]']['name'], L.local_MR['seq_step[2088]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[88]']['name'], L.local_MR['seq_step[88]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[88]']['name'], L.local_T['move_static_timer[88]']['addr'])
      L.ANPB(L.local_MR['seq_step[88]']['name'], L.local_MR['seq_step[88]']['addr'])
      L.OR(L.local_MR['seq_step[2088]']['name'], L.local_MR['seq_step[2088]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2088]']['name'], L.local_MR['seq_step[2088]']['addr'])
      #;Post-Process:moveP@33
      #;timeout:moveP@33
      L.LD(L.local_MR['seq_step[88]']['name'], L.local_MR['seq_step[88]']['addr'])
      L.TMS(L.local_T['block_timeout[88]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[88]']['name'], L.local_T['block_timeout[88]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+88, message='moveP@33:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+88, error_yaml=error_yaml)
      #;error:moveP@33
      L.LD(L.local_MR['seq_step[88]']['name'], L.local_MR['seq_step[88]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+88, message=f"moveP@33:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+88, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+88, message='moveP@33:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+88, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+88, message='moveP@33:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+88, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@33
      L.LDP(L.local_MR['seq_step[88]']['name'], L.local_MR['seq_step[88]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(98.001, -447.154, 283.73, 177.598, 2.269, -46.0, 100.0, 100.0, 100.0, 5.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, override)
        RAC.send_command(f'moveAbsolutePtp({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')
      L.LD(L.local_MR['seq_step[88]']['name'], L.local_MR['seq_step[88]']['addr'])
      L.ANB(L.local_MR['seq_step[2088]']['name'], L.local_MR['seq_step[2088]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')
      L.LD(L.local_MR['seq_step[88]']['name'], L.local_MR['seq_step[88]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[88]']['addr'], 0.0)


      #;Process:procedures_defnoreturn@10
      L.LD(L.local_MR['seq_step[27]']['name'], L.local_MR['seq_step[27]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2089]']['name'], L.local_MR['seq_step[2089]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[89]']['name'], L.local_MR['seq_step[89]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.ANPB(L.local_MR['seq_step[89]']['name'], L.local_MR['seq_step[89]']['addr'])
      L.OR(L.local_MR['seq_step[2089]']['name'], L.local_MR['seq_step[2089]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2089]']['name'], L.local_MR['seq_step[2089]']['addr'])
      #;Post-Process:procedures_defnoreturn@10

      #;Process:moveP@34
      L.LD(L.local_MR['seq_step[2089]']['name'], L.local_MR['seq_step[2089]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2090]']['name'], L.local_MR['seq_step[2090]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[90]']['name'], L.local_MR['seq_step[90]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[90]']['name'], L.local_T['move_static_timer[90]']['addr'])
      L.ANPB(L.local_MR['seq_step[90]']['name'], L.local_MR['seq_step[90]']['addr'])
      L.OR(L.local_MR['seq_step[2090]']['name'], L.local_MR['seq_step[2090]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2090]']['name'], L.local_MR['seq_step[2090]']['addr'])
      #;Post-Process:moveP@34
      #;timeout:moveP@34
      L.LD(L.local_MR['seq_step[90]']['name'], L.local_MR['seq_step[90]']['addr'])
      L.TMS(L.local_T['block_timeout[90]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[90]']['name'], L.local_T['block_timeout[90]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+90, message='moveP@34:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+90, error_yaml=error_yaml)
      #;error:moveP@34
      L.LD(L.local_MR['seq_step[90]']['name'], L.local_MR['seq_step[90]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+90, message=f"moveP@34:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+90, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+90, message='moveP@34:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+90, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+90, message='moveP@34:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+90, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@34
      L.LDP(L.local_MR['seq_step[90]']['name'], L.local_MR['seq_step[90]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(-5.636, -385.171, 293.263, -178.655, 0.129, -136.541, 100.0, 100.0, 100.0, 5.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, override)
        RAC.send_command(f'moveAbsolutePtp({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')
      L.LD(L.local_MR['seq_step[90]']['name'], L.local_MR['seq_step[90]']['addr'])
      L.ANB(L.local_MR['seq_step[2090]']['name'], L.local_MR['seq_step[2090]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')
      L.LD(L.local_MR['seq_step[90]']['name'], L.local_MR['seq_step[90]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[90]']['addr'], 0.0)

      #;Process:moveP@35
      L.LD(L.local_MR['seq_step[2090]']['name'], L.local_MR['seq_step[2090]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2091]']['name'], L.local_MR['seq_step[2091]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[91]']['name'], L.local_MR['seq_step[91]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[91]']['name'], L.local_T['move_static_timer[91]']['addr'])
      L.ANPB(L.local_MR['seq_step[91]']['name'], L.local_MR['seq_step[91]']['addr'])
      L.OR(L.local_MR['seq_step[2091]']['name'], L.local_MR['seq_step[2091]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2091]']['name'], L.local_MR['seq_step[2091]']['addr'])
      #;Post-Process:moveP@35
      #;timeout:moveP@35
      L.LD(L.local_MR['seq_step[91]']['name'], L.local_MR['seq_step[91]']['addr'])
      L.TMS(L.local_T['block_timeout[91]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[91]']['name'], L.local_T['block_timeout[91]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+91, message='moveP@35:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+91, error_yaml=error_yaml)
      #;error:moveP@35
      L.LD(L.local_MR['seq_step[91]']['name'], L.local_MR['seq_step[91]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+91, message=f"moveP@35:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+91, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+91, message='moveP@35:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+91, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+91, message='moveP@35:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+91, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@35
      L.LDP(L.local_MR['seq_step[91]']['name'], L.local_MR['seq_step[91]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(155.208, -385.21, 212.794, -178.69, 0.139, -136.467, 100.0, 100.0, 100.0, 5.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, override)
        RAC.send_command(f'moveAbsolutePtp({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')
      L.LD(L.local_MR['seq_step[91]']['name'], L.local_MR['seq_step[91]']['addr'])
      L.ANB(L.local_MR['seq_step[2091]']['name'], L.local_MR['seq_step[2091]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')
      L.LD(L.local_MR['seq_step[91]']['name'], L.local_MR['seq_step[91]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[91]']['addr'], 0.0)

      #;Process:moveP@36
      L.LD(L.local_MR['seq_step[2091]']['name'], L.local_MR['seq_step[2091]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2092]']['name'], L.local_MR['seq_step[2092]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[92]']['name'], L.local_MR['seq_step[92]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[92]']['name'], L.local_T['move_static_timer[92]']['addr'])
      L.ANPB(L.local_MR['seq_step[92]']['name'], L.local_MR['seq_step[92]']['addr'])
      L.OR(L.local_MR['seq_step[2092]']['name'], L.local_MR['seq_step[2092]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2092]']['name'], L.local_MR['seq_step[2092]']['addr'])
      #;Post-Process:moveP@36
      #;timeout:moveP@36
      L.LD(L.local_MR['seq_step[92]']['name'], L.local_MR['seq_step[92]']['addr'])
      L.TMS(L.local_T['block_timeout[92]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[92]']['name'], L.local_T['block_timeout[92]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+92, message='moveP@36:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+92, error_yaml=error_yaml)
      #;error:moveP@36
      L.LD(L.local_MR['seq_step[92]']['name'], L.local_MR['seq_step[92]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+92, message=f"moveP@36:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+92, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+92, message='moveP@36:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+92, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+92, message='moveP@36:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+92, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@36
      L.LDP(L.local_MR['seq_step[92]']['name'], L.local_MR['seq_step[92]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(155.201, -385.149, 182.635, -178.707, 0.151, -136.468, 100.0, 100.0, 100.0, 0.2, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, override)
        RAC.send_command(f'moveAbsolutePtp({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')
      L.LD(L.local_MR['seq_step[92]']['name'], L.local_MR['seq_step[92]']['addr'])
      L.ANB(L.local_MR['seq_step[2092]']['name'], L.local_MR['seq_step[2092]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')
      L.LD(L.local_MR['seq_step[92]']['name'], L.local_MR['seq_step[92]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[92]']['addr'], 0.0)

      #;Process:procedures_callnoreturn@13
      L.LD(L.local_MR['seq_step[2092]']['name'], L.local_MR['seq_step[2092]']['addr'])
      L.MPS()
      L.LDB(L.local_MR['seq_step[2093]']['name'], L.local_MR['seq_step[2093]']['addr'])
      L.ANB(L.local_MR['seq_step[2072]']['name'], L.local_MR['seq_step[2072]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[93]']['name'], L.local_MR['seq_step[93]']['addr'])
      L.MPP()
      L.LD(L.local_MR['seq_step[2072]']['name'], L.local_MR['seq_step[2072]']['addr'])
      L.ANPB(L.local_MR['seq_step[93]']['name'], L.local_MR['seq_step[93]']['addr'])
      L.OR(L.local_MR['seq_step[2093]']['name'], L.local_MR['seq_step[2093]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2093]']['name'], L.local_MR['seq_step[2093]']['addr'])
      #;Post-Process:procedures_callnoreturn@13

      #;Process:wait_timer@9
      L.LD(L.local_MR['seq_step[2093]']['name'], L.local_MR['seq_step[2093]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2094]']['name'], L.local_MR['seq_step[2094]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[94]']['name'], L.local_MR['seq_step[94]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(L.local_T['block_timer1[94]']['name'], L.local_T['block_timer1[94]']['addr'])
      L.OR(L.local_MR['seq_step[2094]']['name'], L.local_MR['seq_step[2094]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2094]']['name'], L.local_MR['seq_step[2094]']['addr'])
      #;Post-Process:wait_timer@9
      #;timeout:wait_timer@9
      L.LD(L.local_MR['seq_step[94]']['name'], L.local_MR['seq_step[94]']['addr'])
      L.TMS(L.local_T['block_timeout[94]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[94]']['name'], L.local_T['block_timeout[94]']['addr'])
      if (L.aax & L.iix):
        drive.register_error(no=801+94, message='wait_timer@9:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+94, error_yaml=error_yaml)
      #;action:wait_timer@9
      L.LD(L.local_MR['seq_step[94]']['name'], L.local_MR['seq_step[94]']['addr'])
      L.TMS(L.local_T['block_timer1[94]']['addr'], wait_msec=number_param_yaml['N483']['value'])

      #;Process:moveP@37
      L.LD(L.local_MR['seq_step[2094]']['name'], L.local_MR['seq_step[2094]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2095]']['name'], L.local_MR['seq_step[2095]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[95]']['name'], L.local_MR['seq_step[95]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[95]']['name'], L.local_T['move_static_timer[95]']['addr'])
      L.ANPB(L.local_MR['seq_step[95]']['name'], L.local_MR['seq_step[95]']['addr'])
      L.OR(L.local_MR['seq_step[2095]']['name'], L.local_MR['seq_step[2095]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2095]']['name'], L.local_MR['seq_step[2095]']['addr'])
      #;Post-Process:moveP@37
      #;timeout:moveP@37
      L.LD(L.local_MR['seq_step[95]']['name'], L.local_MR['seq_step[95]']['addr'])
      L.TMS(L.local_T['block_timeout[95]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[95]']['name'], L.local_T['block_timeout[95]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+95, message='moveP@37:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+95, error_yaml=error_yaml)
      #;error:moveP@37
      L.LD(L.local_MR['seq_step[95]']['name'], L.local_MR['seq_step[95]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+95, message=f"moveP@37:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+95, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+95, message='moveP@37:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+95, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+95, message='moveP@37:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+95, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@37
      L.LDP(L.local_MR['seq_step[95]']['name'], L.local_MR['seq_step[95]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(155.208, -385.21, 212.794, -178.69, 0.139, -136.467, 100.0, 100.0, 100.0, 5.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, override)
        RAC.send_command(f'moveAbsolutePtp({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')
      L.LD(L.local_MR['seq_step[95]']['name'], L.local_MR['seq_step[95]']['addr'])
      L.ANB(L.local_MR['seq_step[2095]']['name'], L.local_MR['seq_step[2095]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')
      L.LD(L.local_MR['seq_step[95]']['name'], L.local_MR['seq_step[95]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[95]']['addr'], 0.0)

      #;Process:moveP@38
      L.LD(L.local_MR['seq_step[2095]']['name'], L.local_MR['seq_step[2095]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2096]']['name'], L.local_MR['seq_step[2096]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[96]']['name'], L.local_MR['seq_step[96]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[96]']['name'], L.local_T['move_static_timer[96]']['addr'])
      L.ANPB(L.local_MR['seq_step[96]']['name'], L.local_MR['seq_step[96]']['addr'])
      L.OR(L.local_MR['seq_step[2096]']['name'], L.local_MR['seq_step[2096]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2096]']['name'], L.local_MR['seq_step[2096]']['addr'])
      #;Post-Process:moveP@38
      #;timeout:moveP@38
      L.LD(L.local_MR['seq_step[96]']['name'], L.local_MR['seq_step[96]']['addr'])
      L.TMS(L.local_T['block_timeout[96]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[96]']['name'], L.local_T['block_timeout[96]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+96, message='moveP@38:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+96, error_yaml=error_yaml)
      #;error:moveP@38
      L.LD(L.local_MR['seq_step[96]']['name'], L.local_MR['seq_step[96]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+96, message=f"moveP@38:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+96, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+96, message='moveP@38:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+96, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+96, message='moveP@38:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+96, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@38
      L.LDP(L.local_MR['seq_step[96]']['name'], L.local_MR['seq_step[96]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(-5.636, -385.171, 293.263, -178.655, 0.129, -136.541, 100.0, 100.0, 100.0, 5.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, override)
        RAC.send_command(f'moveAbsolutePtp({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')
      L.LD(L.local_MR['seq_step[96]']['name'], L.local_MR['seq_step[96]']['addr'])
      L.ANB(L.local_MR['seq_step[2096]']['name'], L.local_MR['seq_step[2096]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')
      L.LD(L.local_MR['seq_step[96]']['name'], L.local_MR['seq_step[96]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[96]']['addr'], 0.0)


      #;Process:procedures_defnoreturn@11
      L.LD(L.local_MR['seq_step[28]']['name'], L.local_MR['seq_step[28]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2097]']['name'], L.local_MR['seq_step[2097]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[97]']['name'], L.local_MR['seq_step[97]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.ANPB(L.local_MR['seq_step[97]']['name'], L.local_MR['seq_step[97]']['addr'])
      L.OR(L.local_MR['seq_step[2097]']['name'], L.local_MR['seq_step[2097]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2097]']['name'], L.local_MR['seq_step[2097]']['addr'])
      #;Post-Process:procedures_defnoreturn@11

      #;Process:moveP@39
      L.LD(L.local_MR['seq_step[2097]']['name'], L.local_MR['seq_step[2097]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2098]']['name'], L.local_MR['seq_step[2098]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[98]']['name'], L.local_MR['seq_step[98]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[98]']['name'], L.local_T['move_static_timer[98]']['addr'])
      L.ANPB(L.local_MR['seq_step[98]']['name'], L.local_MR['seq_step[98]']['addr'])
      L.OR(L.local_MR['seq_step[2098]']['name'], L.local_MR['seq_step[2098]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2098]']['name'], L.local_MR['seq_step[2098]']['addr'])
      #;Post-Process:moveP@39
      #;timeout:moveP@39
      L.LD(L.local_MR['seq_step[98]']['name'], L.local_MR['seq_step[98]']['addr'])
      L.TMS(L.local_T['block_timeout[98]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[98]']['name'], L.local_T['block_timeout[98]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+98, message='moveP@39:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+98, error_yaml=error_yaml)
      #;error:moveP@39
      L.LD(L.local_MR['seq_step[98]']['name'], L.local_MR['seq_step[98]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+98, message=f"moveP@39:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+98, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+98, message='moveP@39:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+98, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+98, message='moveP@39:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+98, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@39
      L.LDP(L.local_MR['seq_step[98]']['name'], L.local_MR['seq_step[98]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(27.103, -384.901, -68.763, -178.706, 0.283, -136.52, 100.0, 100.0, 100.0, 5.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, override)
        RAC.send_command(f'moveAbsolutePtp({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')
      L.LD(L.local_MR['seq_step[98]']['name'], L.local_MR['seq_step[98]']['addr'])
      L.ANB(L.local_MR['seq_step[2098]']['name'], L.local_MR['seq_step[2098]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')
      L.LD(L.local_MR['seq_step[98]']['name'], L.local_MR['seq_step[98]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[98]']['addr'], 0.0)

      #;Process:moveP@40
      L.LD(L.local_MR['seq_step[2098]']['name'], L.local_MR['seq_step[2098]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2099]']['name'], L.local_MR['seq_step[2099]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[99]']['name'], L.local_MR['seq_step[99]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[99]']['name'], L.local_T['move_static_timer[99]']['addr'])
      L.ANPB(L.local_MR['seq_step[99]']['name'], L.local_MR['seq_step[99]']['addr'])
      L.OR(L.local_MR['seq_step[2099]']['name'], L.local_MR['seq_step[2099]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2099]']['name'], L.local_MR['seq_step[2099]']['addr'])
      #;Post-Process:moveP@40
      #;timeout:moveP@40
      L.LD(L.local_MR['seq_step[99]']['name'], L.local_MR['seq_step[99]']['addr'])
      L.TMS(L.local_T['block_timeout[99]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[99]']['name'], L.local_T['block_timeout[99]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+99, message='moveP@40:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+99, error_yaml=error_yaml)
      #;error:moveP@40
      L.LD(L.local_MR['seq_step[99]']['name'], L.local_MR['seq_step[99]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+99, message=f"moveP@40:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+99, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+99, message='moveP@40:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+99, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+99, message='moveP@40:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+99, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@40
      L.LDP(L.local_MR['seq_step[99]']['name'], L.local_MR['seq_step[99]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(27.103, -384.909, -108.883, -178.705, 0.282, -136.519, 100.0, 100.0, 100.0, 0.2, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, override)
        RAC.send_command(f'moveAbsolutePtp({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')
      L.LD(L.local_MR['seq_step[99]']['name'], L.local_MR['seq_step[99]']['addr'])
      L.ANB(L.local_MR['seq_step[2099]']['name'], L.local_MR['seq_step[2099]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')
      L.LD(L.local_MR['seq_step[99]']['name'], L.local_MR['seq_step[99]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[99]']['addr'], 0.0)

      #;Process:procedures_callnoreturn@14
      L.LD(L.local_MR['seq_step[2099]']['name'], L.local_MR['seq_step[2099]']['addr'])
      L.MPS()
      L.LDB(L.local_MR['seq_step[2100]']['name'], L.local_MR['seq_step[2100]']['addr'])
      L.ANB(L.local_MR['seq_step[2068]']['name'], L.local_MR['seq_step[2068]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[100]']['name'], L.local_MR['seq_step[100]']['addr'])
      L.MPP()
      L.LD(L.local_MR['seq_step[2068]']['name'], L.local_MR['seq_step[2068]']['addr'])
      L.ANPB(L.local_MR['seq_step[100]']['name'], L.local_MR['seq_step[100]']['addr'])
      L.OR(L.local_MR['seq_step[2100]']['name'], L.local_MR['seq_step[2100]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2100]']['name'], L.local_MR['seq_step[2100]']['addr'])
      #;Post-Process:procedures_callnoreturn@14

      #;Process:wait_timer@10
      L.LD(L.local_MR['seq_step[2100]']['name'], L.local_MR['seq_step[2100]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2101]']['name'], L.local_MR['seq_step[2101]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[101]']['name'], L.local_MR['seq_step[101]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(L.local_T['block_timer1[101]']['name'], L.local_T['block_timer1[101]']['addr'])
      L.OR(L.local_MR['seq_step[2101]']['name'], L.local_MR['seq_step[2101]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2101]']['name'], L.local_MR['seq_step[2101]']['addr'])
      #;Post-Process:wait_timer@10
      #;timeout:wait_timer@10
      L.LD(L.local_MR['seq_step[101]']['name'], L.local_MR['seq_step[101]']['addr'])
      L.TMS(L.local_T['block_timeout[101]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[101]']['name'], L.local_T['block_timeout[101]']['addr'])
      if (L.aax & L.iix):
        drive.register_error(no=801+101, message='wait_timer@10:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+101, error_yaml=error_yaml)
      #;action:wait_timer@10
      L.LD(L.local_MR['seq_step[101]']['name'], L.local_MR['seq_step[101]']['addr'])
      L.TMS(L.local_T['block_timer1[101]']['addr'], wait_msec=number_param_yaml['N483']['value'])

      #;Process:moveP@41
      L.LD(L.local_MR['seq_step[2101]']['name'], L.local_MR['seq_step[2101]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2102]']['name'], L.local_MR['seq_step[2102]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[102]']['name'], L.local_MR['seq_step[102]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[102]']['name'], L.local_T['move_static_timer[102]']['addr'])
      L.ANPB(L.local_MR['seq_step[102]']['name'], L.local_MR['seq_step[102]']['addr'])
      L.OR(L.local_MR['seq_step[2102]']['name'], L.local_MR['seq_step[2102]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2102]']['name'], L.local_MR['seq_step[2102]']['addr'])
      #;Post-Process:moveP@41
      #;timeout:moveP@41
      L.LD(L.local_MR['seq_step[102]']['name'], L.local_MR['seq_step[102]']['addr'])
      L.TMS(L.local_T['block_timeout[102]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[102]']['name'], L.local_T['block_timeout[102]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+102, message='moveP@41:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+102, error_yaml=error_yaml)
      #;error:moveP@41
      L.LD(L.local_MR['seq_step[102]']['name'], L.local_MR['seq_step[102]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+102, message=f"moveP@41:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+102, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+102, message='moveP@41:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+102, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+102, message='moveP@41:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+102, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@41
      L.LDP(L.local_MR['seq_step[102]']['name'], L.local_MR['seq_step[102]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(27.103, -384.901, -68.763, -178.706, 0.283, -136.52, 100.0, 100.0, 100.0, 5.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, override)
        RAC.send_command(f'moveAbsolutePtp({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')
      L.LD(L.local_MR['seq_step[102]']['name'], L.local_MR['seq_step[102]']['addr'])
      L.ANB(L.local_MR['seq_step[2102]']['name'], L.local_MR['seq_step[2102]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')
      L.LD(L.local_MR['seq_step[102]']['name'], L.local_MR['seq_step[102]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[102]']['addr'], 0.0)

      #;Process:moveP@42
      L.LD(L.local_MR['seq_step[2102]']['name'], L.local_MR['seq_step[2102]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2103]']['name'], L.local_MR['seq_step[2103]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[103]']['name'], L.local_MR['seq_step[103]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[103]']['name'], L.local_T['move_static_timer[103]']['addr'])
      L.ANPB(L.local_MR['seq_step[103]']['name'], L.local_MR['seq_step[103]']['addr'])
      L.OR(L.local_MR['seq_step[2103]']['name'], L.local_MR['seq_step[2103]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2103]']['name'], L.local_MR['seq_step[2103]']['addr'])
      #;Post-Process:moveP@42
      #;timeout:moveP@42
      L.LD(L.local_MR['seq_step[103]']['name'], L.local_MR['seq_step[103]']['addr'])
      L.TMS(L.local_T['block_timeout[103]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[103]']['name'], L.local_T['block_timeout[103]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+103, message='moveP@42:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+103, error_yaml=error_yaml)
      #;error:moveP@42
      L.LD(L.local_MR['seq_step[103]']['name'], L.local_MR['seq_step[103]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+103, message=f"moveP@42:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+103, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+103, message='moveP@42:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+103, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+103, message='moveP@42:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+103, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@42
      L.LDP(L.local_MR['seq_step[103]']['name'], L.local_MR['seq_step[103]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(-5.636, -385.171, 293.263, -178.655, 0.129, -136.541, 100.0, 100.0, 100.0, 5.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, override)
        RAC.send_command(f'moveAbsolutePtp({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')
      L.LD(L.local_MR['seq_step[103]']['name'], L.local_MR['seq_step[103]']['addr'])
      L.ANB(L.local_MR['seq_step[2103]']['name'], L.local_MR['seq_step[2103]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')
      L.LD(L.local_MR['seq_step[103]']['name'], L.local_MR['seq_step[103]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[103]']['addr'], 0.0)


      #;Process:procedures_defnoreturn@12
      L.LD(L.local_MR['seq_step[29]']['name'], L.local_MR['seq_step[29]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2104]']['name'], L.local_MR['seq_step[2104]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[104]']['name'], L.local_MR['seq_step[104]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.ANPB(L.local_MR['seq_step[104]']['name'], L.local_MR['seq_step[104]']['addr'])
      L.OR(L.local_MR['seq_step[2104]']['name'], L.local_MR['seq_step[2104]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2104]']['name'], L.local_MR['seq_step[2104]']['addr'])
      #;Post-Process:procedures_defnoreturn@12

      #;Process:moveP@44
      L.LD(L.local_MR['seq_step[2104]']['name'], L.local_MR['seq_step[2104]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2105]']['name'], L.local_MR['seq_step[2105]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[105]']['name'], L.local_MR['seq_step[105]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[105]']['name'], L.local_T['move_static_timer[105]']['addr'])
      L.ANPB(L.local_MR['seq_step[105]']['name'], L.local_MR['seq_step[105]']['addr'])
      L.OR(L.local_MR['seq_step[2105]']['name'], L.local_MR['seq_step[2105]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2105]']['name'], L.local_MR['seq_step[2105]']['addr'])
      #;Post-Process:moveP@44
      #;timeout:moveP@44
      L.LD(L.local_MR['seq_step[105]']['name'], L.local_MR['seq_step[105]']['addr'])
      L.TMS(L.local_T['block_timeout[105]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[105]']['name'], L.local_T['block_timeout[105]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+105, message='moveP@44:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+105, error_yaml=error_yaml)
      #;error:moveP@44
      L.LD(L.local_MR['seq_step[105]']['name'], L.local_MR['seq_step[105]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+105, message=f"moveP@44:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+105, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+105, message='moveP@44:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+105, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+105, message='moveP@44:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+105, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@44
      L.LDP(L.local_MR['seq_step[105]']['name'], L.local_MR['seq_step[105]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(98.001, -447.154, 283.73, 177.598, 2.269, -46.0, 100.0, 100.0, 100.0, 5.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, override)
        RAC.send_command(f'moveAbsolutePtp({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')
      L.LD(L.local_MR['seq_step[105]']['name'], L.local_MR['seq_step[105]']['addr'])
      L.ANB(L.local_MR['seq_step[2105]']['name'], L.local_MR['seq_step[2105]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')
      L.LD(L.local_MR['seq_step[105]']['name'], L.local_MR['seq_step[105]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[105]']['addr'], 0.0)

      #;Process:moveP@45
      L.LD(L.local_MR['seq_step[2105]']['name'], L.local_MR['seq_step[2105]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2106]']['name'], L.local_MR['seq_step[2106]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[106]']['name'], L.local_MR['seq_step[106]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[106]']['name'], L.local_T['move_static_timer[106]']['addr'])
      L.ANPB(L.local_MR['seq_step[106]']['name'], L.local_MR['seq_step[106]']['addr'])
      L.OR(L.local_MR['seq_step[2106]']['name'], L.local_MR['seq_step[2106]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2106]']['name'], L.local_MR['seq_step[2106]']['addr'])
      #;Post-Process:moveP@45
      #;timeout:moveP@45
      L.LD(L.local_MR['seq_step[106]']['name'], L.local_MR['seq_step[106]']['addr'])
      L.TMS(L.local_T['block_timeout[106]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[106]']['name'], L.local_T['block_timeout[106]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+106, message='moveP@45:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+106, error_yaml=error_yaml)
      #;error:moveP@45
      L.LD(L.local_MR['seq_step[106]']['name'], L.local_MR['seq_step[106]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+106, message=f"moveP@45:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+106, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+106, message='moveP@45:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+106, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+106, message='moveP@45:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+106, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@45
      L.LDP(L.local_MR['seq_step[106]']['name'], L.local_MR['seq_step[106]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(97.996, -879.312, 169.168, 177.598, 2.27, -46.001, 100.0, 100.0, 100.0, 5.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, override)
        RAC.send_command(f'moveAbsolutePtp({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')
      L.LD(L.local_MR['seq_step[106]']['name'], L.local_MR['seq_step[106]']['addr'])
      L.ANB(L.local_MR['seq_step[2106]']['name'], L.local_MR['seq_step[2106]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')
      L.LD(L.local_MR['seq_step[106]']['name'], L.local_MR['seq_step[106]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[106]']['addr'], 0.0)

      #;Process:moveP@46
      L.LD(L.local_MR['seq_step[2106]']['name'], L.local_MR['seq_step[2106]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2107]']['name'], L.local_MR['seq_step[2107]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[107]']['name'], L.local_MR['seq_step[107]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[107]']['name'], L.local_T['move_static_timer[107]']['addr'])
      L.ANPB(L.local_MR['seq_step[107]']['name'], L.local_MR['seq_step[107]']['addr'])
      L.OR(L.local_MR['seq_step[2107]']['name'], L.local_MR['seq_step[2107]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2107]']['name'], L.local_MR['seq_step[2107]']['addr'])
      #;Post-Process:moveP@46
      #;timeout:moveP@46
      L.LD(L.local_MR['seq_step[107]']['name'], L.local_MR['seq_step[107]']['addr'])
      L.TMS(L.local_T['block_timeout[107]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[107]']['name'], L.local_T['block_timeout[107]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+107, message='moveP@46:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+107, error_yaml=error_yaml)
      #;error:moveP@46
      L.LD(L.local_MR['seq_step[107]']['name'], L.local_MR['seq_step[107]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+107, message=f"moveP@46:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+107, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+107, message='moveP@46:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+107, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+107, message='moveP@46:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+107, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@46
      L.LDP(L.local_MR['seq_step[107]']['name'], L.local_MR['seq_step[107]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(97.999, -879.311, 111.098, 177.599, 2.27, -46.001, 100.0, 100.0, 100.0, 0.2, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, override)
        RAC.send_command(f'moveAbsolutePtp({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')
      L.LD(L.local_MR['seq_step[107]']['name'], L.local_MR['seq_step[107]']['addr'])
      L.ANB(L.local_MR['seq_step[2107]']['name'], L.local_MR['seq_step[2107]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')
      L.LD(L.local_MR['seq_step[107]']['name'], L.local_MR['seq_step[107]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[107]']['addr'], 0.0)

      #;Process:procedures_callnoreturn@6
      L.LD(L.local_MR['seq_step[2107]']['name'], L.local_MR['seq_step[2107]']['addr'])
      L.MPS()
      L.LDB(L.local_MR['seq_step[2108]']['name'], L.local_MR['seq_step[2108]']['addr'])
      L.ANB(L.local_MR['seq_step[2049]']['name'], L.local_MR['seq_step[2049]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[108]']['name'], L.local_MR['seq_step[108]']['addr'])
      L.MPP()
      L.LD(L.local_MR['seq_step[2049]']['name'], L.local_MR['seq_step[2049]']['addr'])
      L.ANPB(L.local_MR['seq_step[108]']['name'], L.local_MR['seq_step[108]']['addr'])
      L.OR(L.local_MR['seq_step[2108]']['name'], L.local_MR['seq_step[2108]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2108]']['name'], L.local_MR['seq_step[2108]']['addr'])
      #;Post-Process:procedures_callnoreturn@6

      #;Process:wait_timer@8
      L.LD(L.local_MR['seq_step[2108]']['name'], L.local_MR['seq_step[2108]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2109]']['name'], L.local_MR['seq_step[2109]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[109]']['name'], L.local_MR['seq_step[109]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(L.local_T['block_timer1[109]']['name'], L.local_T['block_timer1[109]']['addr'])
      L.OR(L.local_MR['seq_step[2109]']['name'], L.local_MR['seq_step[2109]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2109]']['name'], L.local_MR['seq_step[2109]']['addr'])
      #;Post-Process:wait_timer@8
      #;timeout:wait_timer@8
      L.LD(L.local_MR['seq_step[109]']['name'], L.local_MR['seq_step[109]']['addr'])
      L.TMS(L.local_T['block_timeout[109]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[109]']['name'], L.local_T['block_timeout[109]']['addr'])
      if (L.aax & L.iix):
        drive.register_error(no=801+109, message='wait_timer@8:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+109, error_yaml=error_yaml)
      #;action:wait_timer@8
      L.LD(L.local_MR['seq_step[109]']['name'], L.local_MR['seq_step[109]']['addr'])
      L.TMS(L.local_T['block_timer1[109]']['addr'], wait_msec=number_param_yaml['N483']['value'])

      #;Process:moveP@47
      L.LD(L.local_MR['seq_step[2109]']['name'], L.local_MR['seq_step[2109]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2110]']['name'], L.local_MR['seq_step[2110]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[110]']['name'], L.local_MR['seq_step[110]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[110]']['name'], L.local_T['move_static_timer[110]']['addr'])
      L.ANPB(L.local_MR['seq_step[110]']['name'], L.local_MR['seq_step[110]']['addr'])
      L.OR(L.local_MR['seq_step[2110]']['name'], L.local_MR['seq_step[2110]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2110]']['name'], L.local_MR['seq_step[2110]']['addr'])
      #;Post-Process:moveP@47
      #;timeout:moveP@47
      L.LD(L.local_MR['seq_step[110]']['name'], L.local_MR['seq_step[110]']['addr'])
      L.TMS(L.local_T['block_timeout[110]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[110]']['name'], L.local_T['block_timeout[110]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+110, message='moveP@47:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+110, error_yaml=error_yaml)
      #;error:moveP@47
      L.LD(L.local_MR['seq_step[110]']['name'], L.local_MR['seq_step[110]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+110, message=f"moveP@47:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+110, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+110, message='moveP@47:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+110, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+110, message='moveP@47:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+110, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@47
      L.LDP(L.local_MR['seq_step[110]']['name'], L.local_MR['seq_step[110]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(97.996, -879.312, 169.168, 177.598, 2.27, -46.001, 100.0, 100.0, 100.0, 5.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, override)
        RAC.send_command(f'moveAbsolutePtp({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')
      L.LD(L.local_MR['seq_step[110]']['name'], L.local_MR['seq_step[110]']['addr'])
      L.ANB(L.local_MR['seq_step[2110]']['name'], L.local_MR['seq_step[2110]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')
      L.LD(L.local_MR['seq_step[110]']['name'], L.local_MR['seq_step[110]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[110]']['addr'], 0.0)

      #;Process:moveP@48
      L.LD(L.local_MR['seq_step[2110]']['name'], L.local_MR['seq_step[2110]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2111]']['name'], L.local_MR['seq_step[2111]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[111]']['name'], L.local_MR['seq_step[111]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[111]']['name'], L.local_T['move_static_timer[111]']['addr'])
      L.ANPB(L.local_MR['seq_step[111]']['name'], L.local_MR['seq_step[111]']['addr'])
      L.OR(L.local_MR['seq_step[2111]']['name'], L.local_MR['seq_step[2111]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2111]']['name'], L.local_MR['seq_step[2111]']['addr'])
      #;Post-Process:moveP@48
      #;timeout:moveP@48
      L.LD(L.local_MR['seq_step[111]']['name'], L.local_MR['seq_step[111]']['addr'])
      L.TMS(L.local_T['block_timeout[111]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[111]']['name'], L.local_T['block_timeout[111]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+111, message='moveP@48:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+111, error_yaml=error_yaml)
      #;error:moveP@48
      L.LD(L.local_MR['seq_step[111]']['name'], L.local_MR['seq_step[111]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+111, message=f"moveP@48:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+111, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+111, message='moveP@48:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+111, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+111, message='moveP@48:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+111, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@48
      L.LDP(L.local_MR['seq_step[111]']['name'], L.local_MR['seq_step[111]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(98.001, -447.154, 283.73, 177.598, 2.269, -46.0, 100.0, 100.0, 100.0, 5.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, override)
        RAC.send_command(f'moveAbsolutePtp({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')
      L.LD(L.local_MR['seq_step[111]']['name'], L.local_MR['seq_step[111]']['addr'])
      L.ANB(L.local_MR['seq_step[2111]']['name'], L.local_MR['seq_step[2111]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')
      L.LD(L.local_MR['seq_step[111]']['name'], L.local_MR['seq_step[111]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[111]']['addr'], 0.0)

      #;Process:moveP@55
      L.LD(L.local_MR['seq_step[2111]']['name'], L.local_MR['seq_step[2111]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2112]']['name'], L.local_MR['seq_step[2112]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[112]']['name'], L.local_MR['seq_step[112]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[112]']['name'], L.local_T['move_static_timer[112]']['addr'])
      L.ANPB(L.local_MR['seq_step[112]']['name'], L.local_MR['seq_step[112]']['addr'])
      L.OR(L.local_MR['seq_step[2112]']['name'], L.local_MR['seq_step[2112]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2112]']['name'], L.local_MR['seq_step[2112]']['addr'])
      #;Post-Process:moveP@55
      #;timeout:moveP@55
      L.LD(L.local_MR['seq_step[112]']['name'], L.local_MR['seq_step[112]']['addr'])
      L.TMS(L.local_T['block_timeout[112]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[112]']['name'], L.local_T['block_timeout[112]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+112, message='moveP@55:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+112, error_yaml=error_yaml)
      #;error:moveP@55
      L.LD(L.local_MR['seq_step[112]']['name'], L.local_MR['seq_step[112]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+112, message=f"moveP@55:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+112, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+112, message='moveP@55:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+112, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+112, message='moveP@55:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+112, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@55
      L.LDP(L.local_MR['seq_step[112]']['name'], L.local_MR['seq_step[112]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(-136.262, -515.952, 51.038, 179.763, -0.423, -170.288, 100.0, 100.0, 100.0, 5.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, override)
        RAC.send_command(f'moveAbsolutePtp({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')
      L.LD(L.local_MR['seq_step[112]']['name'], L.local_MR['seq_step[112]']['addr'])
      L.ANB(L.local_MR['seq_step[2112]']['name'], L.local_MR['seq_step[2112]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')
      L.LD(L.local_MR['seq_step[112]']['name'], L.local_MR['seq_step[112]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[112]']['addr'], 0.0)


      #;Process:procedures_defnoreturn@13
      L.LD(L.local_MR['seq_step[30]']['name'], L.local_MR['seq_step[30]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2113]']['name'], L.local_MR['seq_step[2113]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[113]']['name'], L.local_MR['seq_step[113]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.ANPB(L.local_MR['seq_step[113]']['name'], L.local_MR['seq_step[113]']['addr'])
      L.OR(L.local_MR['seq_step[2113]']['name'], L.local_MR['seq_step[2113]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2113]']['name'], L.local_MR['seq_step[2113]']['addr'])
      #;Post-Process:procedures_defnoreturn@13

      #;Process:moveP@49
      L.LD(L.local_MR['seq_step[2113]']['name'], L.local_MR['seq_step[2113]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2114]']['name'], L.local_MR['seq_step[2114]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[114]']['name'], L.local_MR['seq_step[114]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[114]']['name'], L.local_T['move_static_timer[114]']['addr'])
      L.ANPB(L.local_MR['seq_step[114]']['name'], L.local_MR['seq_step[114]']['addr'])
      L.OR(L.local_MR['seq_step[2114]']['name'], L.local_MR['seq_step[2114]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2114]']['name'], L.local_MR['seq_step[2114]']['addr'])
      #;Post-Process:moveP@49
      #;timeout:moveP@49
      L.LD(L.local_MR['seq_step[114]']['name'], L.local_MR['seq_step[114]']['addr'])
      L.TMS(L.local_T['block_timeout[114]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[114]']['name'], L.local_T['block_timeout[114]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+114, message='moveP@49:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+114, error_yaml=error_yaml)
      #;error:moveP@49
      L.LD(L.local_MR['seq_step[114]']['name'], L.local_MR['seq_step[114]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+114, message=f"moveP@49:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+114, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+114, message='moveP@49:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+114, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+114, message='moveP@49:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+114, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@49
      L.LDP(L.local_MR['seq_step[114]']['name'], L.local_MR['seq_step[114]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(-67.102, -385.178, -76.847, -178.657, 0.125, 46.471, 100.0, 100.0, 100.0, 5.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, override)
        RAC.send_command(f'moveAbsolutePtp({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')
      L.LD(L.local_MR['seq_step[114]']['name'], L.local_MR['seq_step[114]']['addr'])
      L.ANB(L.local_MR['seq_step[2114]']['name'], L.local_MR['seq_step[2114]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')
      L.LD(L.local_MR['seq_step[114]']['name'], L.local_MR['seq_step[114]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[114]']['addr'], 0.0)

      #;Process:moveP@50
      L.LD(L.local_MR['seq_step[2114]']['name'], L.local_MR['seq_step[2114]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2115]']['name'], L.local_MR['seq_step[2115]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[115]']['name'], L.local_MR['seq_step[115]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[115]']['name'], L.local_T['move_static_timer[115]']['addr'])
      L.ANPB(L.local_MR['seq_step[115]']['name'], L.local_MR['seq_step[115]']['addr'])
      L.OR(L.local_MR['seq_step[2115]']['name'], L.local_MR['seq_step[2115]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2115]']['name'], L.local_MR['seq_step[2115]']['addr'])
      #;Post-Process:moveP@50
      #;timeout:moveP@50
      L.LD(L.local_MR['seq_step[115]']['name'], L.local_MR['seq_step[115]']['addr'])
      L.TMS(L.local_T['block_timeout[115]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[115]']['name'], L.local_T['block_timeout[115]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+115, message='moveP@50:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+115, error_yaml=error_yaml)
      #;error:moveP@50
      L.LD(L.local_MR['seq_step[115]']['name'], L.local_MR['seq_step[115]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+115, message=f"moveP@50:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+115, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+115, message='moveP@50:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+115, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+115, message='moveP@50:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+115, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@50
      L.LDP(L.local_MR['seq_step[115]']['name'], L.local_MR['seq_step[115]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(-67.101, -385.175, -112.909, -178.657, 0.124, 46.471, 100.0, 100.0, 100.0, 0.2, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, override)
        RAC.send_command(f'moveAbsolutePtp({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')
      L.LD(L.local_MR['seq_step[115]']['name'], L.local_MR['seq_step[115]']['addr'])
      L.ANB(L.local_MR['seq_step[2115]']['name'], L.local_MR['seq_step[2115]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')
      L.LD(L.local_MR['seq_step[115]']['name'], L.local_MR['seq_step[115]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[115]']['addr'], 0.0)

      #;Process:procedures_callnoreturn@7
      L.LD(L.local_MR['seq_step[2115]']['name'], L.local_MR['seq_step[2115]']['addr'])
      L.MPS()
      L.LDB(L.local_MR['seq_step[2116]']['name'], L.local_MR['seq_step[2116]']['addr'])
      L.ANB(L.local_MR['seq_step[2045]']['name'], L.local_MR['seq_step[2045]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[116]']['name'], L.local_MR['seq_step[116]']['addr'])
      L.MPP()
      L.LD(L.local_MR['seq_step[2045]']['name'], L.local_MR['seq_step[2045]']['addr'])
      L.ANPB(L.local_MR['seq_step[116]']['name'], L.local_MR['seq_step[116]']['addr'])
      L.OR(L.local_MR['seq_step[2116]']['name'], L.local_MR['seq_step[2116]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2116]']['name'], L.local_MR['seq_step[2116]']['addr'])
      #;Post-Process:procedures_callnoreturn@7

      #;Process:moveP@51
      L.LD(L.local_MR['seq_step[2116]']['name'], L.local_MR['seq_step[2116]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2117]']['name'], L.local_MR['seq_step[2117]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[117]']['name'], L.local_MR['seq_step[117]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[117]']['name'], L.local_T['move_static_timer[117]']['addr'])
      L.ANPB(L.local_MR['seq_step[117]']['name'], L.local_MR['seq_step[117]']['addr'])
      L.OR(L.local_MR['seq_step[2117]']['name'], L.local_MR['seq_step[2117]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2117]']['name'], L.local_MR['seq_step[2117]']['addr'])
      #;Post-Process:moveP@51
      #;timeout:moveP@51
      L.LD(L.local_MR['seq_step[117]']['name'], L.local_MR['seq_step[117]']['addr'])
      L.TMS(L.local_T['block_timeout[117]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[117]']['name'], L.local_T['block_timeout[117]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+117, message='moveP@51:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+117, error_yaml=error_yaml)
      #;error:moveP@51
      L.LD(L.local_MR['seq_step[117]']['name'], L.local_MR['seq_step[117]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+117, message=f"moveP@51:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+117, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+117, message='moveP@51:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+117, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+117, message='moveP@51:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+117, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@51
      L.LDP(L.local_MR['seq_step[117]']['name'], L.local_MR['seq_step[117]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(-67.102, -385.178, -76.847, -178.657, 0.125, 46.471, 100.0, 100.0, 100.0, 5.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, override)
        RAC.send_command(f'moveAbsolutePtp({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')
      L.LD(L.local_MR['seq_step[117]']['name'], L.local_MR['seq_step[117]']['addr'])
      L.ANB(L.local_MR['seq_step[2117]']['name'], L.local_MR['seq_step[2117]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')
      L.LD(L.local_MR['seq_step[117]']['name'], L.local_MR['seq_step[117]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[117]']['addr'], 0.0)

      #;Process:moveP@52
      L.LD(L.local_MR['seq_step[2117]']['name'], L.local_MR['seq_step[2117]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2118]']['name'], L.local_MR['seq_step[2118]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[118]']['name'], L.local_MR['seq_step[118]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[118]']['name'], L.local_T['move_static_timer[118]']['addr'])
      L.ANPB(L.local_MR['seq_step[118]']['name'], L.local_MR['seq_step[118]']['addr'])
      L.OR(L.local_MR['seq_step[2118]']['name'], L.local_MR['seq_step[2118]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2118]']['name'], L.local_MR['seq_step[2118]']['addr'])
      #;Post-Process:moveP@52
      #;timeout:moveP@52
      L.LD(L.local_MR['seq_step[118]']['name'], L.local_MR['seq_step[118]']['addr'])
      L.TMS(L.local_T['block_timeout[118]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[118]']['name'], L.local_T['block_timeout[118]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+118, message='moveP@52:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+118, error_yaml=error_yaml)
      #;error:moveP@52
      L.LD(L.local_MR['seq_step[118]']['name'], L.local_MR['seq_step[118]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+118, message=f"moveP@52:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+118, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+118, message='moveP@52:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+118, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+118, message='moveP@52:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+118, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@52
      L.LDP(L.local_MR['seq_step[118]']['name'], L.local_MR['seq_step[118]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(172.402, -366.352, 311.891, 178.93, 0.583, -136.958, 100.0, 100.0, 100.0, 5.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, override)
        RAC.send_command(f'moveAbsolutePtp({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')
      L.LD(L.local_MR['seq_step[118]']['name'], L.local_MR['seq_step[118]']['addr'])
      L.ANB(L.local_MR['seq_step[2118]']['name'], L.local_MR['seq_step[2118]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')
      L.LD(L.local_MR['seq_step[118]']['name'], L.local_MR['seq_step[118]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[118]']['addr'], 0.0)

      #;Process:return@1
      L.LD(L.local_MR['seq_step[2118]']['name'], L.local_MR['seq_step[2118]']['addr'])
      L.MPS()
      L.ANB(L.local_MR['seq_step[2119]']['name'], L.local_MR['seq_step[2119]']['addr'])
      L.OUT(L.local_MR['seq_step[119]']['name'], L.local_MR['seq_step[119]']['addr'])
      L.MPP()
      L.LDPB(L.local_MR['seq_step[119]']['name'], L.local_MR['seq_step[119]']['addr'])
      L.OR(L.local_MR['seq_step[2119]']['name'], L.local_MR['seq_step[2119]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2119]']['name'], L.local_MR['seq_step[2119]']['addr'])
      #;Post-Process:return@1
      #;action:return@1
      L.LDP(L.local_MR['seq_step[119]']['name'], L.local_MR['seq_step[119]']['addr'])
      if (L.aax & L.iix):
        elapsed_time = int((time.perf_counter() - start_time) * 1000)
        L.EM_relay[2020:2020+len(helper.int32_to_uint16s(elapsed_time))] = helper.int32_to_uint16s(elapsed_time)

    except Exception as e:  
      if(RAC.connected): RAC.send_command('stopRobot()')
      func.cleanup()
      print(e)
      sys.exit(-1)

