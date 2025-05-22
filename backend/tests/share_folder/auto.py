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
from lib.io.contec import cdio_api
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
override = 60
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

      #;Process:select_robot@1
      L.LD(L.local_R['program_start[0]']['name'], L.local_R['program_start[0]']['addr'])
      L.MPS()
      L.LDB(L.local_MR['seq_step[2000]']['name'], L.local_MR['seq_step[2000]']['addr'])
      L.ANB(RAC.connected)
      L.ANL()
      L.OUT(L.local_MR['seq_step[0]']['name'], L.local_MR['seq_step[0]']['addr'])
      L.MPP()
      L.LD(RAC.connected)
      L.OR(L.local_MR['seq_step[2000]']['name'], L.local_MR['seq_step[2000]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2000]']['name'], L.local_MR['seq_step[2000]']['addr'])
      #;Post-Process:select_robot@1
      #;action:select_robot@1
      if(RAC.connected):
        RAC.send_command('getRobotStatus()')
        RAC.send_command('updateRedis()')
        robot_status = RAC.get_status()
        drive.handle_auto_sidebar(robot_status, number_param_yaml, flag_param_yaml)
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
      L.LD(L.local_MR['seq_step[2000]']['name'], L.local_MR['seq_step[2000]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2001]']['name'], L.local_MR['seq_step[2001]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1]']['name'], L.local_MR['seq_step[1]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(L.local_MR['servo_success[0]']['name'], L.local_MR['servo_success[0]']['addr'])
      L.AND(robot_status['servo'])
      L.OR(L.local_MR['seq_step[2001]']['name'], L.local_MR['seq_step[2001]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2001]']['name'], L.local_MR['seq_step[2001]']['addr'])
      #;Post-Process:set_motor@1
      #;action:set_motor@1
      L.LD(L.local_MR['seq_step[1]']['name'], L.local_MR['seq_step[1]']['addr'])
      L.ANB(L.local_MR['servo_success[0]']['name'], L.local_MR['servo_success[0]']['addr'])
      if (L.aax & L.iix):
        success = RAC.send_command('setServoOn()')
        if (success): L.setRelay(L.local_MR['servo_success[0]']['name'], L.local_MR['servo_success[0]']['addr'])
        else        : L.resetRelay(L.local_MR['servo_success[0]']['name'], L.local_MR['servo_success[0]']['addr'])

      #;Process:moveL@1
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
      #;Post-Process:moveL@1
      #;error:moveL@1
      L.LD(L.local_MR['seq_step[2]']['name'], L.local_MR['seq_step[2]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+2, message=f"moveL@1:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+2, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+2, message='moveL@1:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+2, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+2, message='moveL@1:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+2, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveL@1
      L.LDP(L.local_MR['seq_step[2]']['name'], L.local_MR['seq_step[2]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(current_pos['x'], current_pos['y'], 42.285, current_pos['rx'], current_pos['ry'], current_pos['rz'], 100.0, 100.0, 100.0, 0.1, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, override)
        RAC.send_command(f'moveAbsoluteLine({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')
      L.LD(L.local_MR['seq_step[2]']['name'], L.local_MR['seq_step[2]']['addr'])
      L.ANB(L.local_MR['seq_step[2002]']['name'], L.local_MR['seq_step[2002]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')
      L.LD(L.local_MR['seq_step[2]']['name'], L.local_MR['seq_step[2]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[2]']['addr'], 0.0)

      #;Process:moveL@2
      L.LD(L.local_MR['seq_step[2002]']['name'], L.local_MR['seq_step[2002]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2003]']['name'], L.local_MR['seq_step[2003]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[3]']['name'], L.local_MR['seq_step[3]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[3]']['name'], L.local_T['move_static_timer[3]']['addr'])
      L.ANPB(L.local_MR['seq_step[3]']['name'], L.local_MR['seq_step[3]']['addr'])
      L.OR(L.local_MR['seq_step[2003]']['name'], L.local_MR['seq_step[2003]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2003]']['name'], L.local_MR['seq_step[2003]']['addr'])
      #;Post-Process:moveL@2
      #;error:moveL@2
      L.LD(L.local_MR['seq_step[3]']['name'], L.local_MR['seq_step[3]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+3, message=f"moveL@2:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+3, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+3, message='moveL@2:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+3, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+3, message='moveL@2:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+3, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveL@2
      L.LDP(L.local_MR['seq_step[3]']['name'], L.local_MR['seq_step[3]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(247.146, 10.0, current_pos['z'], 0.0, 0.0, -32.643, 100.0, 100.0, 100.0, 0.1, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, override)
        RAC.send_command(f'moveAbsoluteLine({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')
      L.LD(L.local_MR['seq_step[3]']['name'], L.local_MR['seq_step[3]']['addr'])
      L.ANB(L.local_MR['seq_step[2003]']['name'], L.local_MR['seq_step[2003]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')
      L.LD(L.local_MR['seq_step[3]']['name'], L.local_MR['seq_step[3]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[3]']['addr'], 0.0)

      #;Process:loop@1
      L.LD(L.local_MR['seq_step[2003]']['name'], L.local_MR['seq_step[2003]']['addr'])
      L.ANB(L.local_MR['seq_step[2011]']['name'], L.local_MR['seq_step[2011]']['addr'])
      L.MPS()
      L.ANB(L.local_MR['seq_step[2004]']['name'], L.local_MR['seq_step[2004]']['addr'])
      L.OUT(L.local_MR['seq_step[4]']['name'], L.local_MR['seq_step[4]']['addr'])
      L.MPP()
      L.LDPB(L.local_MR['seq_step[4]']['name'], L.local_MR['seq_step[4]']['addr'])
      L.OR(L.local_MR['seq_step[2004]']['name'], L.local_MR['seq_step[2004]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2004]']['name'], L.local_MR['seq_step[2004]']['addr'])
      #;Post-Process:loop@1
      #;action:loop@1
      L.LD(L.local_MR['seq_step[4]']['name'], L.local_MR['seq_step[4]']['addr'])
      if (L.aax & L.iix):
        start_time = time.perf_counter()

      #;Process:moveL@3
      L.LD(L.local_MR['seq_step[2004]']['name'], L.local_MR['seq_step[2004]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2005]']['name'], L.local_MR['seq_step[2005]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[5]']['name'], L.local_MR['seq_step[5]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[5]']['name'], L.local_T['move_static_timer[5]']['addr'])
      L.ANPB(L.local_MR['seq_step[5]']['name'], L.local_MR['seq_step[5]']['addr'])
      L.OR(L.local_MR['seq_step[2005]']['name'], L.local_MR['seq_step[2005]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2005]']['name'], L.local_MR['seq_step[2005]']['addr'])
      #;Post-Process:moveL@3
      #;error:moveL@3
      L.LD(L.local_MR['seq_step[5]']['name'], L.local_MR['seq_step[5]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+5, message=f"moveL@3:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+5, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+5, message='moveL@3:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+5, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+5, message='moveL@3:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+5, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveL@3
      L.LDP(L.local_MR['seq_step[5]']['name'], L.local_MR['seq_step[5]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(227.146, -10.351, 62.285, 0.0, 0.0, -32.643, 100.0, 100.0, 100.0, 0.1, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, override)
        RAC.send_command(f'moveAbsoluteLine({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')
      L.LD(L.local_MR['seq_step[5]']['name'], L.local_MR['seq_step[5]']['addr'])
      L.ANB(L.local_MR['seq_step[2005]']['name'], L.local_MR['seq_step[2005]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')
      L.LD(L.local_MR['seq_step[5]']['name'], L.local_MR['seq_step[5]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[5]']['addr'], 0.0)

      #;Process:moveL@4
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
      #;Post-Process:moveL@4
      #;error:moveL@4
      L.LD(L.local_MR['seq_step[6]']['name'], L.local_MR['seq_step[6]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+6, message=f"moveL@4:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+6, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+6, message='moveL@4:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+6, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+6, message='moveL@4:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+6, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveL@4
      L.LDP(L.local_MR['seq_step[6]']['name'], L.local_MR['seq_step[6]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(237.146, 0.0, 52.285, 0.0, 0.0, -22.643, 100.0, 100.0, 100.0, 0.1, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, override)
        RAC.send_command(f'moveAbsoluteLine({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')
      L.LD(L.local_MR['seq_step[6]']['name'], L.local_MR['seq_step[6]']['addr'])
      L.ANB(L.local_MR['seq_step[2006]']['name'], L.local_MR['seq_step[2006]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')
      L.LD(L.local_MR['seq_step[6]']['name'], L.local_MR['seq_step[6]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[6]']['addr'], 0.0)

      #;Process:moveL@5
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
      #;Post-Process:moveL@5
      #;error:moveL@5
      L.LD(L.local_MR['seq_step[7]']['name'], L.local_MR['seq_step[7]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+7, message=f"moveL@5:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+7, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+7, message='moveL@5:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+7, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+7, message='moveL@5:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+7, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveL@5
      L.LDP(L.local_MR['seq_step[7]']['name'], L.local_MR['seq_step[7]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(247.146, 10.0, 42.285, 0.0, 0.0, -32.643, 100.0, 100.0, 100.0, 0.1, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, override)
        RAC.send_command(f'moveAbsoluteLine({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')
      L.LD(L.local_MR['seq_step[7]']['name'], L.local_MR['seq_step[7]']['addr'])
      L.ANB(L.local_MR['seq_step[2007]']['name'], L.local_MR['seq_step[2007]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')
      L.LD(L.local_MR['seq_step[7]']['name'], L.local_MR['seq_step[7]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[7]']['addr'], 0.0)

      #;Process:moveL@6
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
      #;Post-Process:moveL@6
      #;error:moveL@6
      L.LD(L.local_MR['seq_step[8]']['name'], L.local_MR['seq_step[8]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+8, message=f"moveL@6:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+8, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+8, message='moveL@6:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+8, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+8, message='moveL@6:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+8, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveL@6
      L.LDP(L.local_MR['seq_step[8]']['name'], L.local_MR['seq_step[8]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(227.146, -10.351, 62.285, 0.0, 0.0, -32.643, 100.0, 100.0, 100.0, 0.1, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, override)
        RAC.send_command(f'moveAbsoluteLine({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')
      L.LD(L.local_MR['seq_step[8]']['name'], L.local_MR['seq_step[8]']['addr'])
      L.ANB(L.local_MR['seq_step[2008]']['name'], L.local_MR['seq_step[2008]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')
      L.LD(L.local_MR['seq_step[8]']['name'], L.local_MR['seq_step[8]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[8]']['addr'], 0.0)

      #;Process:moveL@7
      L.LD(L.local_MR['seq_step[2008]']['name'], L.local_MR['seq_step[2008]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2009]']['name'], L.local_MR['seq_step[2009]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[9]']['name'], L.local_MR['seq_step[9]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[9]']['name'], L.local_T['move_static_timer[9]']['addr'])
      L.ANPB(L.local_MR['seq_step[9]']['name'], L.local_MR['seq_step[9]']['addr'])
      L.OR(L.local_MR['seq_step[2009]']['name'], L.local_MR['seq_step[2009]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2009]']['name'], L.local_MR['seq_step[2009]']['addr'])
      #;Post-Process:moveL@7
      #;error:moveL@7
      L.LD(L.local_MR['seq_step[9]']['name'], L.local_MR['seq_step[9]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+9, message=f"moveL@7:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+9, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+9, message='moveL@7:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+9, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+9, message='moveL@7:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+9, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveL@7
      L.LDP(L.local_MR['seq_step[9]']['name'], L.local_MR['seq_step[9]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(237.146, 0.0, 52.285, 0.0, 0.0, -22.643, 100.0, 100.0, 100.0, 0.1, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, override)
        RAC.send_command(f'moveAbsoluteLine({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')
      L.LD(L.local_MR['seq_step[9]']['name'], L.local_MR['seq_step[9]']['addr'])
      L.ANB(L.local_MR['seq_step[2009]']['name'], L.local_MR['seq_step[2009]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')
      L.LD(L.local_MR['seq_step[9]']['name'], L.local_MR['seq_step[9]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[9]']['addr'], 0.0)

      #;Process:moveL@8
      L.LD(L.local_MR['seq_step[2009]']['name'], L.local_MR['seq_step[2009]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[2010]']['name'], L.local_MR['seq_step[2010]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[10]']['name'], L.local_MR['seq_step[10]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[10]']['name'], L.local_T['move_static_timer[10]']['addr'])
      L.ANPB(L.local_MR['seq_step[10]']['name'], L.local_MR['seq_step[10]']['addr'])
      L.OR(L.local_MR['seq_step[2010]']['name'], L.local_MR['seq_step[2010]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2010]']['name'], L.local_MR['seq_step[2010]']['addr'])
      #;Post-Process:moveL@8
      #;error:moveL@8
      L.LD(L.local_MR['seq_step[10]']['name'], L.local_MR['seq_step[10]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+10, message=f"moveL@8:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+10, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+10, message='moveL@8:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+10, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+10, message='moveL@8:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+10, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveL@8
      L.LDP(L.local_MR['seq_step[10]']['name'], L.local_MR['seq_step[10]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(247.146, 10.0, 42.285, 0.0, 0.0, -32.643, 100.0, 100.0, 100.0, 0.1, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, override)
        RAC.send_command(f'moveAbsoluteLine({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')
      L.LD(L.local_MR['seq_step[10]']['name'], L.local_MR['seq_step[10]']['addr'])
      L.ANB(L.local_MR['seq_step[2010]']['name'], L.local_MR['seq_step[2010]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')
      L.LD(L.local_MR['seq_step[10]']['name'], L.local_MR['seq_step[10]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[10]']['addr'], 0.0)

      #;Process:return@1
      L.LD(L.local_MR['seq_step[2010]']['name'], L.local_MR['seq_step[2010]']['addr'])
      L.MPS()
      L.ANB(L.local_MR['seq_step[2011]']['name'], L.local_MR['seq_step[2011]']['addr'])
      L.OUT(L.local_MR['seq_step[11]']['name'], L.local_MR['seq_step[11]']['addr'])
      L.MPP()
      L.LDPB(L.local_MR['seq_step[11]']['name'], L.local_MR['seq_step[11]']['addr'])
      L.OR(L.local_MR['seq_step[2011]']['name'], L.local_MR['seq_step[2011]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2011]']['name'], L.local_MR['seq_step[2011]']['addr'])
      #;Post-Process:return@1
      #;action:return@1
      L.LDP(L.local_MR['seq_step[11]']['name'], L.local_MR['seq_step[11]']['addr'])
      if (L.aax & L.iix):
        elapsed_time = int((time.perf_counter() - start_time) * 1000)
        L.EM_relay[2020:2020+len(helper.int32_to_uint16s(elapsed_time))] = helper.int32_to_uint16s(elapsed_time)

    except Exception as e:  
      if(RAC.connected): RAC.send_command('stopRobot()')
      func.cleanup()
      print(e)
      sys.exit(-1)

