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

def cleanup_device():
  if(RAC.connected): RAC.send_command('stopRobot()')
  for instance in external_io_instance:
    if instance:
      instance.close()

def signal_handler(sig, frame):
  cleanup_device()
  func.cleanup()
  sys.exit(0)

if os.name == 'nt':
  signal.signal(signal.SIGBREAK, signal_handler) 
elif os.name == 'posix':
  signal.signal(signal.SIGTERM, signal_handler) 

ERROR_INTERVAL = 1

success = False
start_time = x = y = z = rx = ry = rz = vel = acc = dec = dist = stime = tool = 0
program_override = 100
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
robot_status = {'servo': False, 'origin': False, 'arrived': False, 'moving': False, 'error': False, 'error_id': 0, 'current_pos': [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],'input_signal': [False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False]}

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
      drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      L.updateTime()
      L.ldlg = 0x0
      L.aax  = 0x0 
      L.trlg = 0x0 
      L.iix  = 0x01
      func.get_command()
      drive.handle_system_lamp()

      #;Process:select_robot@1
      L.LD(L.local_R['program_start[0]']['name'], L.local_R['program_start[0]']['addr'])
      L.MPS()
      L.LDB(L.local_MR['seq_step[1000]']['name'], L.local_MR['seq_step[1000]']['addr'])
      L.ANB(RAC.connected)
      L.ANL()
      L.OUT(L.local_MR['seq_step[0]']['name'], L.local_MR['seq_step[0]']['addr'])
      L.MPP()
      L.LD(RAC.connected)
      L.OR(L.local_MR['seq_step[1000]']['name'], L.local_MR['seq_step[1000]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1000]']['name'], L.local_MR['seq_step[1000]']['addr'])
      #;Post-Process:select_robot@1
      #;action:select_robot@1
      if(RAC.connected):
        flag_param_yaml['F460']['value'] = L.getRelay(R, 8000)
        flag_param_yaml['F461']['value'] = L.getRelay(R, 8001)
        flag_param_yaml['F462']['value'] = L.getRelay(R, 8002)
        flag_param_yaml['F463']['value'] = L.getRelay(R, 8003)
        flag_param_yaml['F464']['value'] = L.getRelay(R, 8004)
        flag_param_yaml['F465']['value'] = L.getRelay(R, 8005)
        flag_param_yaml['F466']['value'] = L.getRelay(R, 8006)
        flag_param_yaml['F467']['value'] = L.getRelay(R, 8007)
        flag_param_yaml['F468']['value'] = L.getRelay(R, 8008)
        flag_param_yaml['F469']['value'] = L.getRelay(R, 8009)
        flag_param_yaml['F470']['value'] = L.getRelay(R, 8010)
        flag_param_yaml['F471']['value'] = L.getRelay(R, 8011)
        flag_param_yaml['F472']['value'] = L.getRelay(R, 8012)
        flag_param_yaml['F473']['value'] = L.getRelay(R, 8013)
        flag_param_yaml['F474']['value'] = L.getRelay(R, 8014)
        flag_param_yaml['F475']['value'] = L.getRelay(R, 8015)
        flag_param_yaml['F480']['value'] = L.getRelay(MR, 300)
        flag_param_yaml['F481']['value'] = L.getRelay(MR, 302)
        flag_param_yaml['F482']['value'] = L.getRelay(MR, 304)
        flag_param_yaml['F483']['value'] = L.getRelay(MR, 501)
        flag_param_yaml['F484']['value'] = L.getRelay(MR, 307)
        flag_param_yaml['F485']['value'] = L.getRelay(MR, 508)
        RAC.send_command('getRobotStatus()')
        RAC.send_command('updateRedis()')
        robot_status = RAC.get_status()
        drive.handle_auto_sidebar(robot_status, number_param_yaml, flag_param_yaml)
        L.LD(MR, 304)
        if (L.aax & L.iix):
          RAC.send_command('pauseRobot()')
        L.LD(L.local_R['reset_pausing[0]']['name'], L.local_R['reset_pausing[0]']['addr'])
        if (L.aax & L.iix):
          RAC.send_command('resumeRobot()')
        L.LD(MR, 307)
        if (L.aax & L.iix):
          RAC.send_command('stopRobot()')
          RAC.send_command('resetError()')
        if robot_status['current_pos']:
          current_pos['x'] = robot_status['current_pos'][0]
          current_pos['y'] = robot_status['current_pos'][1]
          current_pos['z'] = robot_status['current_pos'][2]
          current_pos['rx'] = robot_status['current_pos'][3]
          current_pos['ry'] = robot_status['current_pos'][4]
          current_pos['rz'] = robot_status['current_pos'][5]
      else:
        RAC.send_command('getRobotStatus()')

      #;Process:set_motor@2
      L.LD(L.local_MR['seq_step[1000]']['name'], L.local_MR['seq_step[1000]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[1]']['name'], L.local_MR['seq_step_reset1[1]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1001]']['name'], L.local_MR['seq_step[1001]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1]']['name'], L.local_MR['seq_step[1]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(L.local_MR['servo_success[0]']['name'], L.local_MR['servo_success[0]']['addr'])
      L.AND(robot_status['servo'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1001]']['name'], L.local_MR['seq_step[1001]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1001]']['name'], L.local_MR['seq_step[1001]']['addr'])
      #;Post-Process:set_motor@2
      #;action:set_motor@2
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[1]']['name'], L.local_MR['seq_step[1]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[0]']['name'], L.local_MR['seq_step_reset1[0]']['addr'])
      L.LD(L.local_MR['seq_step[1]']['name'], L.local_MR['seq_step[1]']['addr'])
      L.ANB(L.local_MR['servo_success[0]']['name'], L.local_MR['servo_success[0]']['addr'])
      if (L.aax & L.iix):
        success = RAC.send_command('setServoOn()')
        if (success): L.setRelay(L.local_MR['servo_success[0]']['name'], L.local_MR['servo_success[0]']['addr'])
        else        : L.resetRelay(L.local_MR['servo_success[0]']['name'], L.local_MR['servo_success[0]']['addr'])

      #;Process:set_number@3
      L.LD(L.local_MR['seq_step[1001]']['name'], L.local_MR['seq_step[1001]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[2]']['name'], L.local_MR['seq_step_reset1[2]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1002]']['name'], L.local_MR['seq_step[1002]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[2]']['name'], L.local_MR['seq_step[2]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.ANPB(L.local_MR['seq_step[2]']['name'], L.local_MR['seq_step[2]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1002]']['name'], L.local_MR['seq_step[1002]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1002]']['name'], L.local_MR['seq_step[1002]']['addr'])
      #;Post-Process:set_number@3
      #;timeout:set_number@3
      L.LD(L.local_MR['seq_step[2]']['name'], L.local_MR['seq_step[2]']['addr'])
      L.TMS(L.local_T['block_timeout[2]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[2]']['name'], L.local_T['block_timeout[2]']['addr'])
      if (L.aax & L.iix):
        drive.register_error(no=801+2, message='set_number@3:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+2, error_yaml=error_yaml)
      #;action:set_number@3
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[2]']['name'], L.local_MR['seq_step[2]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[1]']['name'], L.local_MR['seq_step_reset1[1]']['addr'])
      L.LDP(L.local_MR['seq_step[2]']['name'], L.local_MR['seq_step[2]']['addr'])
      if (L.aax & L.iix):
        number_param_yaml['N1']['value'] = 0

      #;Process:loop@4
      L.LD(L.local_MR['seq_step[1002]']['name'], L.local_MR['seq_step[1002]']['addr'])
      L.ANB(L.local_MR['seq_step[1025]']['name'], L.local_MR['seq_step[1025]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[3]']['name'], L.local_MR['seq_step_reset1[3]']['addr'])
      L.MPS()
      L.ANB(L.local_MR['seq_step[1003]']['name'], L.local_MR['seq_step[1003]']['addr'])
      L.OUT(L.local_MR['seq_step[3]']['name'], L.local_MR['seq_step[3]']['addr'])
      L.MPP()
      L.LDPB(L.local_MR['seq_step[3]']['name'], L.local_MR['seq_step[3]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1003]']['name'], L.local_MR['seq_step[1003]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1003]']['name'], L.local_MR['seq_step[1003]']['addr'])
      #;Post-Process:loop@4
      #;action:loop@4
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[3]']['name'], L.local_MR['seq_step[3]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[2]']['name'], L.local_MR['seq_step_reset1[2]']['addr'])
      L.LD(L.local_MR['seq_step[3]']['name'], L.local_MR['seq_step[3]']['addr'])
      if (L.aax & L.iix):
        start_time = time.perf_counter()

      #;Pre-Process:controls_if@5
      #;Process:controls_if@5
      L.LD(L.local_MR['seq_step[1003]']['name'], L.local_MR['seq_step[1003]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[4]']['name'], L.local_MR['seq_step_reset1[4]']['addr'])
      L.ANB(L.local_MR['seq_step_reset2[4]']['name'], L.local_MR['seq_step_reset2[4]']['addr'])
      L.ANB(L.local_MR['seq_step_reset3[4]']['name'], L.local_MR['seq_step_reset3[4]']['addr'])
      L.ANB(L.local_MR['seq_step_reset4[4]']['name'], L.local_MR['seq_step_reset4[4]']['addr'])
      L.ANB(L.local_MR['seq_step_reset5[4]']['name'], L.local_MR['seq_step_reset5[4]']['addr'])
      L.ANB(L.local_MR['seq_step_reset6[4]']['name'], L.local_MR['seq_step_reset6[4]']['addr'])
      L.ANB(L.local_MR['seq_step_reset7[4]']['name'], L.local_MR['seq_step_reset7[4]']['addr'])
      L.ANB(L.local_MR['seq_step_reset8[4]']['name'], L.local_MR['seq_step_reset8[4]']['addr'])
      L.ANB(L.local_MR['seq_step_reset9[4]']['name'], L.local_MR['seq_step_reset9[4]']['addr'])
      L.ANB(L.local_MR['seq_step_reset10[4]']['name'], L.local_MR['seq_step_reset10[4]']['addr'])
      L.MPS()
      L.ANB(L.local_MR['seq_step[1004]']['name'], L.local_MR['seq_step[1004]']['addr'])
      L.OUT(L.local_MR['seq_step[4]']['name'], L.local_MR['seq_step[4]']['addr'])
      L.MPP()
      L.LD(True if (True) else False)
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1004]']['name'], L.local_MR['seq_step[1004]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1004]']['name'], L.local_MR['seq_step[1004]']['addr'])
      #;Post-Process:controls_if@5
      #;action:controls_if@5
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[4]']['name'], L.local_MR['seq_step[4]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[3]']['name'], L.local_MR['seq_step_reset1[3]']['addr'])

      #;Process:moveP@6
      L.LD(L.local_MR['seq_step[1004]']['name'], L.local_MR['seq_step[1004]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[5]']['name'], L.local_MR['seq_step_reset1[5]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1005]']['name'], L.local_MR['seq_step[1005]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[5]']['name'], L.local_MR['seq_step[5]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[5]']['name'], L.local_T['move_static_timer[5]']['addr'])
      L.ANPB(L.local_MR['seq_step[5]']['name'], L.local_MR['seq_step[5]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1005]']['name'], L.local_MR['seq_step[1005]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1005]']['name'], L.local_MR['seq_step[1005]']['addr'])
      #;Post-Process:moveP@6
      #;timeout:moveP@6
      L.LD(L.local_MR['seq_step[5]']['name'], L.local_MR['seq_step[5]']['addr'])
      L.TMS(L.local_T['block_timeout[5]']['addr'], 60000000)
      L.LDP(L.local_T['block_timeout[5]']['name'], L.local_T['block_timeout[5]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+5, message='moveP@6:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+5, error_yaml=error_yaml)
      #;error:moveP@6
      L.LD(L.local_MR['seq_step[5]']['name'], L.local_MR['seq_step[5]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+5, message=f"moveP@6:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+5, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+5, message='moveP@6:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+5, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+5, message='moveP@6:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+5, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@6
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[5]']['name'], L.local_MR['seq_step[5]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[4]']['name'], L.local_MR['seq_step_reset1[4]']['addr'])
      L.LDP(L.local_MR['seq_step[5]']['name'], L.local_MR['seq_step[5]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool, posture = L.FB_setRobotParam(227.146, -10.351, 62.285, 0.0, 0.0, -32.643, 100.0, 100.0, 100.0, 0.1, 0.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, 60, program_override)
        RAC.send_command(f'moveAbsolutePtp({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {json.dumps({'TOOL': 1, 'USER': 1, 'POSTURE': posture, 'VEL': vel, 'ACC': acc, 'DEC': dec})})')
      L.LD(L.local_MR['seq_step[5]']['name'], L.local_MR['seq_step[5]']['addr'])
      L.ANB(L.local_MR['seq_step[1005]']['name'], L.local_MR['seq_step[1005]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {dist})')
      L.LD(L.local_MR['seq_step[5]']['name'], L.local_MR['seq_step[5]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[5]']['addr'], 0.0)
      L.LD(L.local_MR['seq_step[5]']['name'], L.local_MR['seq_step[5]']['addr'])
      L.OUT(L.local_MR['robot_busy[5]']['name'], L.local_MR['robot_busy[5]']['addr'])

      #;Process:procedures_callnoreturn@8
      L.LD(L.local_MR['seq_step[1005]']['name'], L.local_MR['seq_step[1005]']['addr'])
      L.MPS()
      L.LDB(L.local_MR['seq_step[1006]']['name'], L.local_MR['seq_step[1006]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[6]']['name'], L.local_MR['seq_step[6]']['addr'])
      L.MPP()
      L.LD(L.local_MR['seq_step[1056]']['name'], L.local_MR['seq_step[1056]']['addr'])
      L.ANPB(L.local_MR['seq_step[6]']['name'], L.local_MR['seq_step[6]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1006]']['name'], L.local_MR['seq_step[1006]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1006]']['name'], L.local_MR['seq_step[1006]']['addr'])
      #;Post-Process:procedures_callnoreturn@8
      #;action:procedures_callnoreturn@8
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[6]']['name'], L.local_MR['seq_step[6]']['addr'])
      L.AND(L.local_MR['seq_step[46]']['name'], L.local_MR['seq_step[46]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[5]']['name'], L.local_MR['seq_step_reset1[5]']['addr'])

      #;Process:procedures_callnoreturn@9
      L.LD(L.local_MR['seq_step[1006]']['name'], L.local_MR['seq_step[1006]']['addr'])
      L.MPS()
      L.LDB(L.local_MR['seq_step[1007]']['name'], L.local_MR['seq_step[1007]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[7]']['name'], L.local_MR['seq_step[7]']['addr'])
      L.MPP()
      L.LD(L.local_MR['seq_step[1067]']['name'], L.local_MR['seq_step[1067]']['addr'])
      L.ANPB(L.local_MR['seq_step[7]']['name'], L.local_MR['seq_step[7]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1007]']['name'], L.local_MR['seq_step[1007]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1007]']['name'], L.local_MR['seq_step[1007]']['addr'])
      #;Post-Process:procedures_callnoreturn@9
      #;action:procedures_callnoreturn@9
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[7]']['name'], L.local_MR['seq_step[7]']['addr'])
      L.AND(L.local_MR['seq_step[57]']['name'], L.local_MR['seq_step[57]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[6]']['name'], L.local_MR['seq_step_reset1[6]']['addr'])

      #;Process:moveP@10
      L.LD(L.local_MR['seq_step[1007]']['name'], L.local_MR['seq_step[1007]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[8]']['name'], L.local_MR['seq_step_reset1[8]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1008]']['name'], L.local_MR['seq_step[1008]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[8]']['name'], L.local_MR['seq_step[8]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[8]']['name'], L.local_T['move_static_timer[8]']['addr'])
      L.ANPB(L.local_MR['seq_step[8]']['name'], L.local_MR['seq_step[8]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1008]']['name'], L.local_MR['seq_step[1008]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1008]']['name'], L.local_MR['seq_step[1008]']['addr'])
      #;Post-Process:moveP@10
      #;timeout:moveP@10
      L.LD(L.local_MR['seq_step[8]']['name'], L.local_MR['seq_step[8]']['addr'])
      L.TMS(L.local_T['block_timeout[8]']['addr'], 60000000)
      L.LDP(L.local_T['block_timeout[8]']['name'], L.local_T['block_timeout[8]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+8, message='moveP@10:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+8, error_yaml=error_yaml)
      #;error:moveP@10
      L.LD(L.local_MR['seq_step[8]']['name'], L.local_MR['seq_step[8]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+8, message=f"moveP@10:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+8, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+8, message='moveP@10:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+8, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+8, message='moveP@10:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+8, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@10
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[8]']['name'], L.local_MR['seq_step[8]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[7]']['name'], L.local_MR['seq_step_reset1[7]']['addr'])
      L.LDP(L.local_MR['seq_step[8]']['name'], L.local_MR['seq_step[8]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool, posture = L.FB_setRobotParam(227.146, -10.351, 62.285, 0.0, 0.0, -32.643, 100.0, 100.0, 100.0, 0.1, 0.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, 60, program_override)
        RAC.send_command(f'moveAbsolutePtp({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {json.dumps({'TOOL': 1, 'USER': 1, 'POSTURE': posture, 'VEL': vel, 'ACC': acc, 'DEC': dec})})')
      L.LD(L.local_MR['seq_step[8]']['name'], L.local_MR['seq_step[8]']['addr'])
      L.ANB(L.local_MR['seq_step[1008]']['name'], L.local_MR['seq_step[1008]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {dist})')
      L.LD(L.local_MR['seq_step[8]']['name'], L.local_MR['seq_step[8]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[8]']['addr'], 0.0)
      L.LD(L.local_MR['seq_step[8]']['name'], L.local_MR['seq_step[8]']['addr'])
      L.OUT(L.local_MR['robot_busy[8]']['name'], L.local_MR['robot_busy[8]']['addr'])

      #;Process:wait_input@11
      L.LD(L.local_MR['seq_step[1008]']['name'], L.local_MR['seq_step[1008]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[9]']['name'], L.local_MR['seq_step_reset1[9]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1009]']['name'], L.local_MR['seq_step[1009]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[9]']['name'], L.local_MR['seq_step[9]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(True if robot_status['input_signal'][0] else False)
      L.ANPB(L.local_MR['seq_step[9]']['name'], L.local_MR['seq_step[9]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1009]']['name'], L.local_MR['seq_step[1009]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1009]']['name'], L.local_MR['seq_step[1009]']['addr'])
      #;action:wait_input@11
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[9]']['name'], L.local_MR['seq_step[9]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[8]']['name'], L.local_MR['seq_step_reset1[8]']['addr'])
      L.LD(L.local_MR['seq_step[9]']['name'], L.local_MR['seq_step[9]']['addr'])
      if (L.aax & L.iix):
        RAC.send_command('getInput(0)')
      L.LD(L.local_MR['seq_step[9]']['name'], L.local_MR['seq_step[9]']['addr'])
      L.OUT(L.local_MR['robot_busy[9]']['name'], L.local_MR['robot_busy[9]']['addr'])

      #;Process:procedures_callnoreturn@12
      L.LD(L.local_MR['seq_step[1009]']['name'], L.local_MR['seq_step[1009]']['addr'])
      L.MPS()
      L.LDB(L.local_MR['seq_step[1010]']['name'], L.local_MR['seq_step[1010]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[10]']['name'], L.local_MR['seq_step[10]']['addr'])
      L.MPP()
      L.LD(L.local_MR['seq_step[1077]']['name'], L.local_MR['seq_step[1077]']['addr'])
      L.ANPB(L.local_MR['seq_step[10]']['name'], L.local_MR['seq_step[10]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1010]']['name'], L.local_MR['seq_step[1010]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1010]']['name'], L.local_MR['seq_step[1010]']['addr'])
      #;Post-Process:procedures_callnoreturn@12
      #;action:procedures_callnoreturn@12
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[10]']['name'], L.local_MR['seq_step[10]']['addr'])
      L.AND(L.local_MR['seq_step[68]']['name'], L.local_MR['seq_step[68]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[9]']['name'], L.local_MR['seq_step_reset1[9]']['addr'])

      #;Process:procedures_callnoreturn@13
      L.LD(L.local_MR['seq_step[1010]']['name'], L.local_MR['seq_step[1010]']['addr'])
      L.MPS()
      L.LDB(L.local_MR['seq_step[1011]']['name'], L.local_MR['seq_step[1011]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[11]']['name'], L.local_MR['seq_step[11]']['addr'])
      L.MPP()
      L.LD(L.local_MR['seq_step[1088]']['name'], L.local_MR['seq_step[1088]']['addr'])
      L.ANPB(L.local_MR['seq_step[11]']['name'], L.local_MR['seq_step[11]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1011]']['name'], L.local_MR['seq_step[1011]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1011]']['name'], L.local_MR['seq_step[1011]']['addr'])
      #;Post-Process:procedures_callnoreturn@13
      #;action:procedures_callnoreturn@13
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[11]']['name'], L.local_MR['seq_step[11]']['addr'])
      L.AND(L.local_MR['seq_step[78]']['name'], L.local_MR['seq_step[78]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[10]']['name'], L.local_MR['seq_step_reset1[10]']['addr'])

      #;Process:wait_input@14
      L.LD(L.local_MR['seq_step[1011]']['name'], L.local_MR['seq_step[1011]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[12]']['name'], L.local_MR['seq_step_reset1[12]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1012]']['name'], L.local_MR['seq_step[1012]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[12]']['name'], L.local_MR['seq_step[12]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(True if robot_status['input_signal'][0] else False)
      L.ANPB(L.local_MR['seq_step[12]']['name'], L.local_MR['seq_step[12]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1012]']['name'], L.local_MR['seq_step[1012]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1012]']['name'], L.local_MR['seq_step[1012]']['addr'])
      #;action:wait_input@14
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[12]']['name'], L.local_MR['seq_step[12]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[11]']['name'], L.local_MR['seq_step_reset1[11]']['addr'])
      L.LD(L.local_MR['seq_step[12]']['name'], L.local_MR['seq_step[12]']['addr'])
      if (L.aax & L.iix):
        RAC.send_command('getInput(0)')
      L.LD(L.local_MR['seq_step[12]']['name'], L.local_MR['seq_step[12]']['addr'])
      L.OUT(L.local_MR['robot_busy[12]']['name'], L.local_MR['robot_busy[12]']['addr'])

      #;Process:set_output@15
      L.LD(L.local_MR['seq_step[1012]']['name'], L.local_MR['seq_step[1012]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[13]']['name'], L.local_MR['seq_step_reset1[13]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1013]']['name'], L.local_MR['seq_step[1013]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[13]']['name'], L.local_MR['seq_step[13]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.ANPB(L.local_MR['seq_step[13]']['name'], L.local_MR['seq_step[13]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1013]']['name'], L.local_MR['seq_step[1013]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1013]']['name'], L.local_MR['seq_step[1013]']['addr'])
      #;Post-Process:set_output@15
      #;action:set_output@15
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[13]']['name'], L.local_MR['seq_step[13]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[12]']['name'], L.local_MR['seq_step_reset1[12]']['addr'])
      L.LDP(L.local_MR['seq_step[13]']['name'], L.local_MR['seq_step[13]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        success = RAC.send_command('setOutputON(1)')
      L.LD(L.local_MR['seq_step[13]']['name'], L.local_MR['seq_step[13]']['addr'])
      L.OUT(L.local_MR['robot_busy[13]']['name'], L.local_MR['robot_busy[13]']['addr'])

      #;Process:wait_block@16
      L.LD(L.local_MR['seq_step[1013]']['name'], L.local_MR['seq_step[1013]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[14]']['name'], L.local_MR['seq_step_reset1[14]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1014]']['name'], L.local_MR['seq_step[1014]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[14]']['name'], L.local_MR['seq_step[14]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND((True and True))
      L.ANPB(L.local_MR['seq_step[14]']['name'], L.local_MR['seq_step[14]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1014]']['name'], L.local_MR['seq_step[1014]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1014]']['name'], L.local_MR['seq_step[1014]']['addr'])
      #;action:wait_block@16
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[14]']['name'], L.local_MR['seq_step[14]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[13]']['name'], L.local_MR['seq_step_reset1[13]']['addr'])

      #;Process:procedures_callnoreturn@17
      L.LD(L.local_MR['seq_step[1014]']['name'], L.local_MR['seq_step[1014]']['addr'])
      L.MPS()
      L.LDB(L.local_MR['seq_step[1015]']['name'], L.local_MR['seq_step[1015]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[15]']['name'], L.local_MR['seq_step[15]']['addr'])
      L.MPP()
      L.LD(L.local_MR['seq_step[1099]']['name'], L.local_MR['seq_step[1099]']['addr'])
      L.ANPB(L.local_MR['seq_step[15]']['name'], L.local_MR['seq_step[15]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1015]']['name'], L.local_MR['seq_step[1015]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1015]']['name'], L.local_MR['seq_step[1015]']['addr'])
      #;Post-Process:procedures_callnoreturn@17
      #;action:procedures_callnoreturn@17
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[15]']['name'], L.local_MR['seq_step[15]']['addr'])
      L.AND(L.local_MR['seq_step[89]']['name'], L.local_MR['seq_step[89]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[14]']['name'], L.local_MR['seq_step_reset1[14]']['addr'])

      #;Process:moveP@18
      L.LD(L.local_MR['seq_step[1015]']['name'], L.local_MR['seq_step[1015]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[16]']['name'], L.local_MR['seq_step_reset1[16]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1016]']['name'], L.local_MR['seq_step[1016]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[16]']['name'], L.local_MR['seq_step[16]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[16]']['name'], L.local_T['move_static_timer[16]']['addr'])
      L.ANPB(L.local_MR['seq_step[16]']['name'], L.local_MR['seq_step[16]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1016]']['name'], L.local_MR['seq_step[1016]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1016]']['name'], L.local_MR['seq_step[1016]']['addr'])
      #;Post-Process:moveP@18
      #;timeout:moveP@18
      L.LD(L.local_MR['seq_step[16]']['name'], L.local_MR['seq_step[16]']['addr'])
      L.TMS(L.local_T['block_timeout[16]']['addr'], 60000000)
      L.LDP(L.local_T['block_timeout[16]']['name'], L.local_T['block_timeout[16]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+16, message='moveP@18:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+16, error_yaml=error_yaml)
      #;error:moveP@18
      L.LD(L.local_MR['seq_step[16]']['name'], L.local_MR['seq_step[16]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+16, message=f"moveP@18:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+16, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+16, message='moveP@18:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+16, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+16, message='moveP@18:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+16, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@18
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[16]']['name'], L.local_MR['seq_step[16]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[15]']['name'], L.local_MR['seq_step_reset1[15]']['addr'])
      L.LDP(L.local_MR['seq_step[16]']['name'], L.local_MR['seq_step[16]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool, posture = L.FB_setRobotParam(227.146, -10.351, 62.285, 0.0, 0.0, -32.643, 100.0, 100.0, 100.0, 0.1, 0.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, 60, program_override)
        RAC.send_command(f'moveAbsolutePtp({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {json.dumps({'TOOL': 1, 'USER': 1, 'POSTURE': posture, 'VEL': vel, 'ACC': acc, 'DEC': dec})})')
      L.LD(L.local_MR['seq_step[16]']['name'], L.local_MR['seq_step[16]']['addr'])
      L.ANB(L.local_MR['seq_step[1016]']['name'], L.local_MR['seq_step[1016]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {dist})')
      L.LD(L.local_MR['seq_step[16]']['name'], L.local_MR['seq_step[16]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[16]']['addr'], 0.0)
      L.LD(L.local_MR['seq_step[16]']['name'], L.local_MR['seq_step[16]']['addr'])
      L.OUT(L.local_MR['robot_busy[16]']['name'], L.local_MR['robot_busy[16]']['addr'])

      #;Process:procedures_callnoreturn@19
      L.LD(L.local_MR['seq_step[1016]']['name'], L.local_MR['seq_step[1016]']['addr'])
      L.MPS()
      L.LDB(L.local_MR['seq_step[1017]']['name'], L.local_MR['seq_step[1017]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[17]']['name'], L.local_MR['seq_step[17]']['addr'])
      L.MPP()
      L.LD(L.local_MR['seq_step[1109]']['name'], L.local_MR['seq_step[1109]']['addr'])
      L.ANPB(L.local_MR['seq_step[17]']['name'], L.local_MR['seq_step[17]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1017]']['name'], L.local_MR['seq_step[1017]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1017]']['name'], L.local_MR['seq_step[1017]']['addr'])
      #;Post-Process:procedures_callnoreturn@19
      #;action:procedures_callnoreturn@19
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[17]']['name'], L.local_MR['seq_step[17]']['addr'])
      L.AND(L.local_MR['seq_step[100]']['name'], L.local_MR['seq_step[100]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[16]']['name'], L.local_MR['seq_step_reset1[16]']['addr'])

      #;Process:moveP@20
      L.LD(L.local_MR['seq_step[1017]']['name'], L.local_MR['seq_step[1017]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[18]']['name'], L.local_MR['seq_step_reset1[18]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1018]']['name'], L.local_MR['seq_step[1018]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[18]']['name'], L.local_MR['seq_step[18]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[18]']['name'], L.local_T['move_static_timer[18]']['addr'])
      L.ANPB(L.local_MR['seq_step[18]']['name'], L.local_MR['seq_step[18]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1018]']['name'], L.local_MR['seq_step[1018]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1018]']['name'], L.local_MR['seq_step[1018]']['addr'])
      #;Post-Process:moveP@20
      #;timeout:moveP@20
      L.LD(L.local_MR['seq_step[18]']['name'], L.local_MR['seq_step[18]']['addr'])
      L.TMS(L.local_T['block_timeout[18]']['addr'], 60000000)
      L.LDP(L.local_T['block_timeout[18]']['name'], L.local_T['block_timeout[18]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+18, message='moveP@20:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+18, error_yaml=error_yaml)
      #;error:moveP@20
      L.LD(L.local_MR['seq_step[18]']['name'], L.local_MR['seq_step[18]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+18, message=f"moveP@20:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+18, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+18, message='moveP@20:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+18, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+18, message='moveP@20:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+18, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@20
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[18]']['name'], L.local_MR['seq_step[18]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[17]']['name'], L.local_MR['seq_step_reset1[17]']['addr'])
      L.LDP(L.local_MR['seq_step[18]']['name'], L.local_MR['seq_step[18]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool, posture = L.FB_setRobotParam(227.146, -10.351, 62.285, 0.0, 0.0, -32.643, 100.0, 100.0, 100.0, 0.1, 0.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, 60, program_override)
        RAC.send_command(f'moveAbsolutePtp({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {json.dumps({'TOOL': 1, 'USER': 1, 'POSTURE': posture, 'VEL': vel, 'ACC': acc, 'DEC': dec})})')
      L.LD(L.local_MR['seq_step[18]']['name'], L.local_MR['seq_step[18]']['addr'])
      L.ANB(L.local_MR['seq_step[1018]']['name'], L.local_MR['seq_step[1018]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {dist})')
      L.LD(L.local_MR['seq_step[18]']['name'], L.local_MR['seq_step[18]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[18]']['addr'], 0.0)
      L.LD(L.local_MR['seq_step[18]']['name'], L.local_MR['seq_step[18]']['addr'])
      L.OUT(L.local_MR['robot_busy[18]']['name'], L.local_MR['robot_busy[18]']['addr'])

      #;Process:procedures_callnoreturn@21
      L.LD(L.local_MR['seq_step[1018]']['name'], L.local_MR['seq_step[1018]']['addr'])
      L.MPS()
      L.LDB(L.local_MR['seq_step[1019]']['name'], L.local_MR['seq_step[1019]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[19]']['name'], L.local_MR['seq_step[19]']['addr'])
      L.MPP()
      L.LD(L.local_MR['seq_step[1120]']['name'], L.local_MR['seq_step[1120]']['addr'])
      L.ANPB(L.local_MR['seq_step[19]']['name'], L.local_MR['seq_step[19]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1019]']['name'], L.local_MR['seq_step[1019]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1019]']['name'], L.local_MR['seq_step[1019]']['addr'])
      #;Post-Process:procedures_callnoreturn@21
      #;action:procedures_callnoreturn@21
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[19]']['name'], L.local_MR['seq_step[19]']['addr'])
      L.AND(L.local_MR['seq_step[110]']['name'], L.local_MR['seq_step[110]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[18]']['name'], L.local_MR['seq_step_reset1[18]']['addr'])

      #;Process:procedures_callnoreturn@22
      L.LD(L.local_MR['seq_step[1019]']['name'], L.local_MR['seq_step[1019]']['addr'])
      L.MPS()
      L.LDB(L.local_MR['seq_step[1020]']['name'], L.local_MR['seq_step[1020]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[20]']['name'], L.local_MR['seq_step[20]']['addr'])
      L.MPP()
      L.LD(L.local_MR['seq_step[1130]']['name'], L.local_MR['seq_step[1130]']['addr'])
      L.ANPB(L.local_MR['seq_step[20]']['name'], L.local_MR['seq_step[20]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1020]']['name'], L.local_MR['seq_step[1020]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1020]']['name'], L.local_MR['seq_step[1020]']['addr'])
      #;Post-Process:procedures_callnoreturn@22
      #;action:procedures_callnoreturn@22
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[20]']['name'], L.local_MR['seq_step[20]']['addr'])
      L.AND(L.local_MR['seq_step[121]']['name'], L.local_MR['seq_step[121]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[19]']['name'], L.local_MR['seq_step_reset1[19]']['addr'])

      #;Process:moveP@23
      L.LD(L.local_MR['seq_step[1020]']['name'], L.local_MR['seq_step[1020]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[21]']['name'], L.local_MR['seq_step_reset1[21]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1021]']['name'], L.local_MR['seq_step[1021]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[21]']['name'], L.local_MR['seq_step[21]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[21]']['name'], L.local_T['move_static_timer[21]']['addr'])
      L.ANPB(L.local_MR['seq_step[21]']['name'], L.local_MR['seq_step[21]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1021]']['name'], L.local_MR['seq_step[1021]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1021]']['name'], L.local_MR['seq_step[1021]']['addr'])
      #;Post-Process:moveP@23
      #;timeout:moveP@23
      L.LD(L.local_MR['seq_step[21]']['name'], L.local_MR['seq_step[21]']['addr'])
      L.TMS(L.local_T['block_timeout[21]']['addr'], 60000000)
      L.LDP(L.local_T['block_timeout[21]']['name'], L.local_T['block_timeout[21]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+21, message='moveP@23:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+21, error_yaml=error_yaml)
      #;error:moveP@23
      L.LD(L.local_MR['seq_step[21]']['name'], L.local_MR['seq_step[21]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+21, message=f"moveP@23:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+21, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+21, message='moveP@23:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+21, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+21, message='moveP@23:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+21, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@23
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[21]']['name'], L.local_MR['seq_step[21]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[20]']['name'], L.local_MR['seq_step_reset1[20]']['addr'])
      L.LDP(L.local_MR['seq_step[21]']['name'], L.local_MR['seq_step[21]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool, posture = L.FB_setRobotParam(227.146, -10.351, 62.285, 0.0, 0.0, -32.643, 100.0, 100.0, 100.0, 0.1, 0.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, 60, program_override)
        RAC.send_command(f'moveAbsolutePtp({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {json.dumps({'TOOL': 1, 'USER': 1, 'POSTURE': posture, 'VEL': vel, 'ACC': acc, 'DEC': dec})})')
      L.LD(L.local_MR['seq_step[21]']['name'], L.local_MR['seq_step[21]']['addr'])
      L.ANB(L.local_MR['seq_step[1021]']['name'], L.local_MR['seq_step[1021]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {dist})')
      L.LD(L.local_MR['seq_step[21]']['name'], L.local_MR['seq_step[21]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[21]']['addr'], 0.0)
      L.LD(L.local_MR['seq_step[21]']['name'], L.local_MR['seq_step[21]']['addr'])
      L.OUT(L.local_MR['robot_busy[21]']['name'], L.local_MR['robot_busy[21]']['addr'])

      #;Process:procedures_callnoreturn@24
      L.LD(L.local_MR['seq_step[1021]']['name'], L.local_MR['seq_step[1021]']['addr'])
      L.MPS()
      L.LDB(L.local_MR['seq_step[1022]']['name'], L.local_MR['seq_step[1022]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[22]']['name'], L.local_MR['seq_step[22]']['addr'])
      L.MPP()
      L.LD(L.local_MR['seq_step[1141]']['name'], L.local_MR['seq_step[1141]']['addr'])
      L.ANPB(L.local_MR['seq_step[22]']['name'], L.local_MR['seq_step[22]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1022]']['name'], L.local_MR['seq_step[1022]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1022]']['name'], L.local_MR['seq_step[1022]']['addr'])
      #;Post-Process:procedures_callnoreturn@24
      #;action:procedures_callnoreturn@24
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[22]']['name'], L.local_MR['seq_step[22]']['addr'])
      L.AND(L.local_MR['seq_step[131]']['name'], L.local_MR['seq_step[131]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[21]']['name'], L.local_MR['seq_step_reset1[21]']['addr'])

      #;Process:moveP@25
      L.LD(L.local_MR['seq_step[1022]']['name'], L.local_MR['seq_step[1022]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[23]']['name'], L.local_MR['seq_step_reset1[23]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1023]']['name'], L.local_MR['seq_step[1023]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[23]']['name'], L.local_MR['seq_step[23]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[23]']['name'], L.local_T['move_static_timer[23]']['addr'])
      L.ANPB(L.local_MR['seq_step[23]']['name'], L.local_MR['seq_step[23]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1023]']['name'], L.local_MR['seq_step[1023]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1023]']['name'], L.local_MR['seq_step[1023]']['addr'])
      #;Post-Process:moveP@25
      #;timeout:moveP@25
      L.LD(L.local_MR['seq_step[23]']['name'], L.local_MR['seq_step[23]']['addr'])
      L.TMS(L.local_T['block_timeout[23]']['addr'], 60000000)
      L.LDP(L.local_T['block_timeout[23]']['name'], L.local_T['block_timeout[23]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+23, message='moveP@25:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+23, error_yaml=error_yaml)
      #;error:moveP@25
      L.LD(L.local_MR['seq_step[23]']['name'], L.local_MR['seq_step[23]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+23, message=f"moveP@25:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+23, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+23, message='moveP@25:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+23, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+23, message='moveP@25:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+23, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@25
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[23]']['name'], L.local_MR['seq_step[23]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[22]']['name'], L.local_MR['seq_step_reset1[22]']['addr'])
      L.LDP(L.local_MR['seq_step[23]']['name'], L.local_MR['seq_step[23]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool, posture = L.FB_setRobotParam(227.146, -10.351, 62.285, 0.0, 0.0, -32.643, 100.0, 100.0, 100.0, 0.1, 0.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, 60, program_override)
        RAC.send_command(f'moveAbsolutePtp({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {json.dumps({'TOOL': 1, 'USER': 1, 'POSTURE': posture, 'VEL': vel, 'ACC': acc, 'DEC': dec})})')
      L.LD(L.local_MR['seq_step[23]']['name'], L.local_MR['seq_step[23]']['addr'])
      L.ANB(L.local_MR['seq_step[1023]']['name'], L.local_MR['seq_step[1023]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {dist})')
      L.LD(L.local_MR['seq_step[23]']['name'], L.local_MR['seq_step[23]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[23]']['addr'], 0.0)
      L.LD(L.local_MR['seq_step[23]']['name'], L.local_MR['seq_step[23]']['addr'])
      L.OUT(L.local_MR['robot_busy[23]']['name'], L.local_MR['robot_busy[23]']['addr'])

      #;Process:procedures_callnoreturn@26
      L.LD(L.local_MR['seq_step[1023]']['name'], L.local_MR['seq_step[1023]']['addr'])
      L.MPS()
      L.LDB(L.local_MR['seq_step[1024]']['name'], L.local_MR['seq_step[1024]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[24]']['name'], L.local_MR['seq_step[24]']['addr'])
      L.MPP()
      L.LD(L.local_MR['seq_step[1151]']['name'], L.local_MR['seq_step[1151]']['addr'])
      L.ANPB(L.local_MR['seq_step[24]']['name'], L.local_MR['seq_step[24]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1024]']['name'], L.local_MR['seq_step[1024]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1024]']['name'], L.local_MR['seq_step[1024]']['addr'])
      #;Post-Process:procedures_callnoreturn@26
      #;action:procedures_callnoreturn@26
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[24]']['name'], L.local_MR['seq_step[24]']['addr'])
      L.AND(L.local_MR['seq_step[142]']['name'], L.local_MR['seq_step[142]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[23]']['name'], L.local_MR['seq_step_reset1[23]']['addr'])

      #;Process:return@28
      L.LD(L.local_MR['seq_step[1024]']['name'], L.local_MR['seq_step[1024]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[25]']['name'], L.local_MR['seq_step_reset1[25]']['addr'])
      L.MPS()
      L.ANB(L.local_MR['seq_step[1025]']['name'], L.local_MR['seq_step[1025]']['addr'])
      L.OUT(L.local_MR['seq_step[25]']['name'], L.local_MR['seq_step[25]']['addr'])
      L.MPP()
      L.LDPB(L.local_MR['seq_step[25]']['name'], L.local_MR['seq_step[25]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1025]']['name'], L.local_MR['seq_step[1025]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1025]']['name'], L.local_MR['seq_step[1025]']['addr'])
      #;Post-Process:return@28
      #;action:return@28
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[25]']['name'], L.local_MR['seq_step[25]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[24]']['name'], L.local_MR['seq_step_reset1[24]']['addr'])
      L.LDP(L.local_MR['seq_step[25]']['name'], L.local_MR['seq_step[25]']['addr'])
      if (L.aax & L.iix):
        elapsed_time = int((time.perf_counter() - start_time) * 1000)
        L.EM_relay[2020:2020+len(helper.int32_to_uint16s(elapsed_time))] = helper.int32_to_uint16s(elapsed_time)


      #;Process:procedures_defnoreturn@29
      L.LD(L.local_MR['seq_step[49]']['name'], L.local_MR['seq_step[49]']['addr'])
      L.OR(L.local_MR['seq_step[83]']['name'], L.local_MR['seq_step[83]']['addr'])
      L.OR(L.local_MR['seq_step[113]']['name'], L.local_MR['seq_step[113]']['addr'])
      L.OR(L.local_MR['seq_step[126]']['name'], L.local_MR['seq_step[126]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[26]']['name'], L.local_MR['seq_step_reset1[26]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1026]']['name'], L.local_MR['seq_step[1026]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[26]']['name'], L.local_MR['seq_step[26]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.ANPB(L.local_MR['seq_step[26]']['name'], L.local_MR['seq_step[26]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1026]']['name'], L.local_MR['seq_step[1026]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1026]']['name'], L.local_MR['seq_step[1026]']['addr'])
      #;Post-Process:procedures_defnoreturn@29

      #;Process:wait_timer@30
      L.LD(L.local_MR['seq_step[1026]']['name'], L.local_MR['seq_step[1026]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[27]']['name'], L.local_MR['seq_step_reset1[27]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1027]']['name'], L.local_MR['seq_step[1027]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[27]']['name'], L.local_MR['seq_step[27]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(L.local_T['block_timer1[27]']['name'], L.local_T['block_timer1[27]']['addr'])
      L.ANPB(L.local_MR['seq_step[27]']['name'], L.local_MR['seq_step[27]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1027]']['name'], L.local_MR['seq_step[1027]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1027]']['name'], L.local_MR['seq_step[1027]']['addr'])
      #;Post-Process:wait_timer@30
      #;timeout:wait_timer@30
      L.LD(L.local_MR['seq_step[27]']['name'], L.local_MR['seq_step[27]']['addr'])
      L.TMS(L.local_T['block_timeout[27]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[27]']['name'], L.local_T['block_timeout[27]']['addr'])
      if (L.aax & L.iix):
        drive.register_error(no=801+27, message='wait_timer@30:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+27, error_yaml=error_yaml)
      #;action:wait_timer@30
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[27]']['name'], L.local_MR['seq_step[27]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[26]']['name'], L.local_MR['seq_step_reset1[26]']['addr'])
      L.LD(L.local_MR['seq_step[27]']['name'], L.local_MR['seq_step[27]']['addr'])
      L.TMS(L.local_T['block_timer1[27]']['addr'], wait_msec=number_param_yaml['N1']['value'])

      #;Process:set_output@31
      L.LD(L.local_MR['seq_step[1027]']['name'], L.local_MR['seq_step[1027]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[28]']['name'], L.local_MR['seq_step_reset1[28]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1028]']['name'], L.local_MR['seq_step[1028]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[28]']['name'], L.local_MR['seq_step[28]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.ANPB(L.local_MR['seq_step[28]']['name'], L.local_MR['seq_step[28]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1028]']['name'], L.local_MR['seq_step[1028]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1028]']['name'], L.local_MR['seq_step[1028]']['addr'])
      #;Post-Process:set_output@31
      #;action:set_output@31
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[28]']['name'], L.local_MR['seq_step[28]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[27]']['name'], L.local_MR['seq_step_reset1[27]']['addr'])
      L.LDP(L.local_MR['seq_step[28]']['name'], L.local_MR['seq_step[28]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        success = RAC.send_command('setOutputON(1)')
      L.LD(L.local_MR['seq_step[28]']['name'], L.local_MR['seq_step[28]']['addr'])
      L.OUT(L.local_MR['robot_busy[28]']['name'], L.local_MR['robot_busy[28]']['addr'])

      #;Process:wait_input@32
      L.LD(L.local_MR['seq_step[1028]']['name'], L.local_MR['seq_step[1028]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[29]']['name'], L.local_MR['seq_step_reset1[29]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1029]']['name'], L.local_MR['seq_step[1029]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[29]']['name'], L.local_MR['seq_step[29]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(True if robot_status['input_signal'][0] else False)
      L.ANPB(L.local_MR['seq_step[29]']['name'], L.local_MR['seq_step[29]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1029]']['name'], L.local_MR['seq_step[1029]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1029]']['name'], L.local_MR['seq_step[1029]']['addr'])
      #;action:wait_input@32
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[29]']['name'], L.local_MR['seq_step[29]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[28]']['name'], L.local_MR['seq_step_reset1[28]']['addr'])
      L.LD(L.local_MR['seq_step[29]']['name'], L.local_MR['seq_step[29]']['addr'])
      if (L.aax & L.iix):
        RAC.send_command('getInput(0)')
      L.LD(L.local_MR['seq_step[29]']['name'], L.local_MR['seq_step[29]']['addr'])
      L.OUT(L.local_MR['robot_busy[29]']['name'], L.local_MR['robot_busy[29]']['addr'])

      #;Process:return@33
      L.LD(L.local_MR['seq_step[1029]']['name'], L.local_MR['seq_step[1029]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[30]']['name'], L.local_MR['seq_step_reset1[30]']['addr'])
      L.MPS()
      L.ANB(L.local_MR['seq_step[1030]']['name'], L.local_MR['seq_step[1030]']['addr'])
      L.OUT(L.local_MR['seq_step[30]']['name'], L.local_MR['seq_step[30]']['addr'])
      L.MPP()
      L.LDPB(L.local_MR['seq_step[30]']['name'], L.local_MR['seq_step[30]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1030]']['name'], L.local_MR['seq_step[1030]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1030]']['name'], L.local_MR['seq_step[1030]']['addr'])
      #;Post-Process:return@33
      #;action:return@33
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[30]']['name'], L.local_MR['seq_step[30]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[29]']['name'], L.local_MR['seq_step_reset1[29]']['addr'])
      L.LDP(L.local_MR['seq_step[30]']['name'], L.local_MR['seq_step[30]']['addr'])
      if (L.aax & L.iix):
        elapsed_time = int((time.perf_counter() - start_time) * 1000)
        L.EM_relay[2020:2020+len(helper.int32_to_uint16s(elapsed_time))] = helper.int32_to_uint16s(elapsed_time)


      #;Process:procedures_defnoreturn@34
      L.LD(L.local_MR['seq_step[52]']['name'], L.local_MR['seq_step[52]']['addr'])
      L.OR(L.local_MR['seq_step[116]']['name'], L.local_MR['seq_step[116]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[31]']['name'], L.local_MR['seq_step_reset1[31]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1031]']['name'], L.local_MR['seq_step[1031]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[31]']['name'], L.local_MR['seq_step[31]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.ANPB(L.local_MR['seq_step[31]']['name'], L.local_MR['seq_step[31]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1031]']['name'], L.local_MR['seq_step[1031]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1031]']['name'], L.local_MR['seq_step[1031]']['addr'])
      #;Post-Process:procedures_defnoreturn@34

      #;Process:wait_timer@35
      L.LD(L.local_MR['seq_step[1031]']['name'], L.local_MR['seq_step[1031]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[32]']['name'], L.local_MR['seq_step_reset1[32]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1032]']['name'], L.local_MR['seq_step[1032]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[32]']['name'], L.local_MR['seq_step[32]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(L.local_T['block_timer1[32]']['name'], L.local_T['block_timer1[32]']['addr'])
      L.ANPB(L.local_MR['seq_step[32]']['name'], L.local_MR['seq_step[32]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1032]']['name'], L.local_MR['seq_step[1032]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1032]']['name'], L.local_MR['seq_step[1032]']['addr'])
      #;Post-Process:wait_timer@35
      #;timeout:wait_timer@35
      L.LD(L.local_MR['seq_step[32]']['name'], L.local_MR['seq_step[32]']['addr'])
      L.TMS(L.local_T['block_timeout[32]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[32]']['name'], L.local_T['block_timeout[32]']['addr'])
      if (L.aax & L.iix):
        drive.register_error(no=801+32, message='wait_timer@35:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+32, error_yaml=error_yaml)
      #;action:wait_timer@35
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[32]']['name'], L.local_MR['seq_step[32]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[31]']['name'], L.local_MR['seq_step_reset1[31]']['addr'])
      L.LD(L.local_MR['seq_step[32]']['name'], L.local_MR['seq_step[32]']['addr'])
      L.TMS(L.local_T['block_timer1[32]']['addr'], wait_msec=number_param_yaml['N1']['value'])

      #;Process:set_output@36
      L.LD(L.local_MR['seq_step[1032]']['name'], L.local_MR['seq_step[1032]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[33]']['name'], L.local_MR['seq_step_reset1[33]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1033]']['name'], L.local_MR['seq_step[1033]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[33]']['name'], L.local_MR['seq_step[33]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.ANPB(L.local_MR['seq_step[33]']['name'], L.local_MR['seq_step[33]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1033]']['name'], L.local_MR['seq_step[1033]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1033]']['name'], L.local_MR['seq_step[1033]']['addr'])
      #;Post-Process:set_output@36
      #;action:set_output@36
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[33]']['name'], L.local_MR['seq_step[33]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[32]']['name'], L.local_MR['seq_step_reset1[32]']['addr'])
      L.LDP(L.local_MR['seq_step[33]']['name'], L.local_MR['seq_step[33]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        success = RAC.send_command('setOutputON(1)')
      L.LD(L.local_MR['seq_step[33]']['name'], L.local_MR['seq_step[33]']['addr'])
      L.OUT(L.local_MR['robot_busy[33]']['name'], L.local_MR['robot_busy[33]']['addr'])

      #;Process:wait_input@37
      L.LD(L.local_MR['seq_step[1033]']['name'], L.local_MR['seq_step[1033]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[34]']['name'], L.local_MR['seq_step_reset1[34]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1034]']['name'], L.local_MR['seq_step[1034]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[34]']['name'], L.local_MR['seq_step[34]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(True if robot_status['input_signal'][0] else False)
      L.ANPB(L.local_MR['seq_step[34]']['name'], L.local_MR['seq_step[34]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1034]']['name'], L.local_MR['seq_step[1034]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1034]']['name'], L.local_MR['seq_step[1034]']['addr'])
      #;action:wait_input@37
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[34]']['name'], L.local_MR['seq_step[34]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[33]']['name'], L.local_MR['seq_step_reset1[33]']['addr'])
      L.LD(L.local_MR['seq_step[34]']['name'], L.local_MR['seq_step[34]']['addr'])
      if (L.aax & L.iix):
        RAC.send_command('getInput(0)')
      L.LD(L.local_MR['seq_step[34]']['name'], L.local_MR['seq_step[34]']['addr'])
      L.OUT(L.local_MR['robot_busy[34]']['name'], L.local_MR['robot_busy[34]']['addr'])

      #;Process:return@38
      L.LD(L.local_MR['seq_step[1034]']['name'], L.local_MR['seq_step[1034]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[35]']['name'], L.local_MR['seq_step_reset1[35]']['addr'])
      L.MPS()
      L.ANB(L.local_MR['seq_step[1035]']['name'], L.local_MR['seq_step[1035]']['addr'])
      L.OUT(L.local_MR['seq_step[35]']['name'], L.local_MR['seq_step[35]']['addr'])
      L.MPP()
      L.LDPB(L.local_MR['seq_step[35]']['name'], L.local_MR['seq_step[35]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1035]']['name'], L.local_MR['seq_step[1035]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1035]']['name'], L.local_MR['seq_step[1035]']['addr'])
      #;Post-Process:return@38
      #;action:return@38
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[35]']['name'], L.local_MR['seq_step[35]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[34]']['name'], L.local_MR['seq_step_reset1[34]']['addr'])
      L.LDP(L.local_MR['seq_step[35]']['name'], L.local_MR['seq_step[35]']['addr'])
      if (L.aax & L.iix):
        elapsed_time = int((time.perf_counter() - start_time) * 1000)
        L.EM_relay[2020:2020+len(helper.int32_to_uint16s(elapsed_time))] = helper.int32_to_uint16s(elapsed_time)


      #;Process:procedures_defnoreturn@39
      L.LD(L.local_MR['seq_step[60]']['name'], L.local_MR['seq_step[60]']['addr'])
      L.OR(L.local_MR['seq_step[73]']['name'], L.local_MR['seq_step[73]']['addr'])
      L.OR(L.local_MR['seq_step[92]']['name'], L.local_MR['seq_step[92]']['addr'])
      L.OR(L.local_MR['seq_step[105]']['name'], L.local_MR['seq_step[105]']['addr'])
      L.OR(L.local_MR['seq_step[134]']['name'], L.local_MR['seq_step[134]']['addr'])
      L.OR(L.local_MR['seq_step[147]']['name'], L.local_MR['seq_step[147]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[36]']['name'], L.local_MR['seq_step_reset1[36]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1036]']['name'], L.local_MR['seq_step[1036]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[36]']['name'], L.local_MR['seq_step[36]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.ANPB(L.local_MR['seq_step[36]']['name'], L.local_MR['seq_step[36]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1036]']['name'], L.local_MR['seq_step[1036]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1036]']['name'], L.local_MR['seq_step[1036]']['addr'])
      #;Post-Process:procedures_defnoreturn@39

      #;Process:wait_timer@40
      L.LD(L.local_MR['seq_step[1036]']['name'], L.local_MR['seq_step[1036]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[37]']['name'], L.local_MR['seq_step_reset1[37]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1037]']['name'], L.local_MR['seq_step[1037]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[37]']['name'], L.local_MR['seq_step[37]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(L.local_T['block_timer1[37]']['name'], L.local_T['block_timer1[37]']['addr'])
      L.ANPB(L.local_MR['seq_step[37]']['name'], L.local_MR['seq_step[37]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1037]']['name'], L.local_MR['seq_step[1037]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1037]']['name'], L.local_MR['seq_step[1037]']['addr'])
      #;Post-Process:wait_timer@40
      #;timeout:wait_timer@40
      L.LD(L.local_MR['seq_step[37]']['name'], L.local_MR['seq_step[37]']['addr'])
      L.TMS(L.local_T['block_timeout[37]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[37]']['name'], L.local_T['block_timeout[37]']['addr'])
      if (L.aax & L.iix):
        drive.register_error(no=801+37, message='wait_timer@40:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+37, error_yaml=error_yaml)
      #;action:wait_timer@40
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[37]']['name'], L.local_MR['seq_step[37]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[36]']['name'], L.local_MR['seq_step_reset1[36]']['addr'])
      L.LD(L.local_MR['seq_step[37]']['name'], L.local_MR['seq_step[37]']['addr'])
      L.TMS(L.local_T['block_timer1[37]']['addr'], wait_msec=number_param_yaml['N1']['value'])

      #;Process:set_output@41
      L.LD(L.local_MR['seq_step[1037]']['name'], L.local_MR['seq_step[1037]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[38]']['name'], L.local_MR['seq_step_reset1[38]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1038]']['name'], L.local_MR['seq_step[1038]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[38]']['name'], L.local_MR['seq_step[38]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.ANPB(L.local_MR['seq_step[38]']['name'], L.local_MR['seq_step[38]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1038]']['name'], L.local_MR['seq_step[1038]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1038]']['name'], L.local_MR['seq_step[1038]']['addr'])
      #;Post-Process:set_output@41
      #;action:set_output@41
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[38]']['name'], L.local_MR['seq_step[38]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[37]']['name'], L.local_MR['seq_step_reset1[37]']['addr'])
      L.LDP(L.local_MR['seq_step[38]']['name'], L.local_MR['seq_step[38]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        success = RAC.send_command('setOutputON(1)')
      L.LD(L.local_MR['seq_step[38]']['name'], L.local_MR['seq_step[38]']['addr'])
      L.OUT(L.local_MR['robot_busy[38]']['name'], L.local_MR['robot_busy[38]']['addr'])

      #;Process:wait_input@42
      L.LD(L.local_MR['seq_step[1038]']['name'], L.local_MR['seq_step[1038]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[39]']['name'], L.local_MR['seq_step_reset1[39]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1039]']['name'], L.local_MR['seq_step[1039]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[39]']['name'], L.local_MR['seq_step[39]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(True if robot_status['input_signal'][0] else False)
      L.ANPB(L.local_MR['seq_step[39]']['name'], L.local_MR['seq_step[39]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1039]']['name'], L.local_MR['seq_step[1039]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1039]']['name'], L.local_MR['seq_step[1039]']['addr'])
      #;action:wait_input@42
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[39]']['name'], L.local_MR['seq_step[39]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[38]']['name'], L.local_MR['seq_step_reset1[38]']['addr'])
      L.LD(L.local_MR['seq_step[39]']['name'], L.local_MR['seq_step[39]']['addr'])
      if (L.aax & L.iix):
        RAC.send_command('getInput(0)')
      L.LD(L.local_MR['seq_step[39]']['name'], L.local_MR['seq_step[39]']['addr'])
      L.OUT(L.local_MR['robot_busy[39]']['name'], L.local_MR['robot_busy[39]']['addr'])

      #;Process:return@43
      L.LD(L.local_MR['seq_step[1039]']['name'], L.local_MR['seq_step[1039]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[40]']['name'], L.local_MR['seq_step_reset1[40]']['addr'])
      L.MPS()
      L.ANB(L.local_MR['seq_step[1040]']['name'], L.local_MR['seq_step[1040]']['addr'])
      L.OUT(L.local_MR['seq_step[40]']['name'], L.local_MR['seq_step[40]']['addr'])
      L.MPP()
      L.LDPB(L.local_MR['seq_step[40]']['name'], L.local_MR['seq_step[40]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1040]']['name'], L.local_MR['seq_step[1040]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1040]']['name'], L.local_MR['seq_step[1040]']['addr'])
      #;Post-Process:return@43
      #;action:return@43
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[40]']['name'], L.local_MR['seq_step[40]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[39]']['name'], L.local_MR['seq_step_reset1[39]']['addr'])
      L.LDP(L.local_MR['seq_step[40]']['name'], L.local_MR['seq_step[40]']['addr'])
      if (L.aax & L.iix):
        elapsed_time = int((time.perf_counter() - start_time) * 1000)
        L.EM_relay[2020:2020+len(helper.int32_to_uint16s(elapsed_time))] = helper.int32_to_uint16s(elapsed_time)


      #;Process:procedures_defnoreturn@44
      L.LD(L.local_MR['seq_step[63]']['name'], L.local_MR['seq_step[63]']['addr'])
      L.OR(L.local_MR['seq_step[95]']['name'], L.local_MR['seq_step[95]']['addr'])
      L.OR(L.local_MR['seq_step[137]']['name'], L.local_MR['seq_step[137]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[41]']['name'], L.local_MR['seq_step_reset1[41]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1041]']['name'], L.local_MR['seq_step[1041]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[41]']['name'], L.local_MR['seq_step[41]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.ANPB(L.local_MR['seq_step[41]']['name'], L.local_MR['seq_step[41]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1041]']['name'], L.local_MR['seq_step[1041]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1041]']['name'], L.local_MR['seq_step[1041]']['addr'])
      #;Post-Process:procedures_defnoreturn@44

      #;Process:wait_timer@45
      L.LD(L.local_MR['seq_step[1041]']['name'], L.local_MR['seq_step[1041]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[42]']['name'], L.local_MR['seq_step_reset1[42]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1042]']['name'], L.local_MR['seq_step[1042]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[42]']['name'], L.local_MR['seq_step[42]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(L.local_T['block_timer1[42]']['name'], L.local_T['block_timer1[42]']['addr'])
      L.ANPB(L.local_MR['seq_step[42]']['name'], L.local_MR['seq_step[42]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1042]']['name'], L.local_MR['seq_step[1042]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1042]']['name'], L.local_MR['seq_step[1042]']['addr'])
      #;Post-Process:wait_timer@45
      #;timeout:wait_timer@45
      L.LD(L.local_MR['seq_step[42]']['name'], L.local_MR['seq_step[42]']['addr'])
      L.TMS(L.local_T['block_timeout[42]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[42]']['name'], L.local_T['block_timeout[42]']['addr'])
      if (L.aax & L.iix):
        drive.register_error(no=801+42, message='wait_timer@45:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+42, error_yaml=error_yaml)
      #;action:wait_timer@45
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[42]']['name'], L.local_MR['seq_step[42]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[41]']['name'], L.local_MR['seq_step_reset1[41]']['addr'])
      L.LD(L.local_MR['seq_step[42]']['name'], L.local_MR['seq_step[42]']['addr'])
      L.TMS(L.local_T['block_timer1[42]']['addr'], wait_msec=number_param_yaml['N1']['value'])

      #;Process:set_output@46
      L.LD(L.local_MR['seq_step[1042]']['name'], L.local_MR['seq_step[1042]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[43]']['name'], L.local_MR['seq_step_reset1[43]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1043]']['name'], L.local_MR['seq_step[1043]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[43]']['name'], L.local_MR['seq_step[43]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.ANPB(L.local_MR['seq_step[43]']['name'], L.local_MR['seq_step[43]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1043]']['name'], L.local_MR['seq_step[1043]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1043]']['name'], L.local_MR['seq_step[1043]']['addr'])
      #;Post-Process:set_output@46
      #;action:set_output@46
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[43]']['name'], L.local_MR['seq_step[43]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[42]']['name'], L.local_MR['seq_step_reset1[42]']['addr'])
      L.LDP(L.local_MR['seq_step[43]']['name'], L.local_MR['seq_step[43]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        success = RAC.send_command('setOutputON(1)')
      L.LD(L.local_MR['seq_step[43]']['name'], L.local_MR['seq_step[43]']['addr'])
      L.OUT(L.local_MR['robot_busy[43]']['name'], L.local_MR['robot_busy[43]']['addr'])

      #;Process:wait_input@47
      L.LD(L.local_MR['seq_step[1043]']['name'], L.local_MR['seq_step[1043]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[44]']['name'], L.local_MR['seq_step_reset1[44]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1044]']['name'], L.local_MR['seq_step[1044]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[44]']['name'], L.local_MR['seq_step[44]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(True if robot_status['input_signal'][0] else False)
      L.ANPB(L.local_MR['seq_step[44]']['name'], L.local_MR['seq_step[44]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1044]']['name'], L.local_MR['seq_step[1044]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1044]']['name'], L.local_MR['seq_step[1044]']['addr'])
      #;action:wait_input@47
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[44]']['name'], L.local_MR['seq_step[44]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[43]']['name'], L.local_MR['seq_step_reset1[43]']['addr'])
      L.LD(L.local_MR['seq_step[44]']['name'], L.local_MR['seq_step[44]']['addr'])
      if (L.aax & L.iix):
        RAC.send_command('getInput(0)')
      L.LD(L.local_MR['seq_step[44]']['name'], L.local_MR['seq_step[44]']['addr'])
      L.OUT(L.local_MR['robot_busy[44]']['name'], L.local_MR['robot_busy[44]']['addr'])

      #;Process:return@48
      L.LD(L.local_MR['seq_step[1044]']['name'], L.local_MR['seq_step[1044]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[45]']['name'], L.local_MR['seq_step_reset1[45]']['addr'])
      L.MPS()
      L.ANB(L.local_MR['seq_step[1045]']['name'], L.local_MR['seq_step[1045]']['addr'])
      L.OUT(L.local_MR['seq_step[45]']['name'], L.local_MR['seq_step[45]']['addr'])
      L.MPP()
      L.LDPB(L.local_MR['seq_step[45]']['name'], L.local_MR['seq_step[45]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1045]']['name'], L.local_MR['seq_step[1045]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1045]']['name'], L.local_MR['seq_step[1045]']['addr'])
      #;Post-Process:return@48
      #;action:return@48
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[45]']['name'], L.local_MR['seq_step[45]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[44]']['name'], L.local_MR['seq_step_reset1[44]']['addr'])
      L.LDP(L.local_MR['seq_step[45]']['name'], L.local_MR['seq_step[45]']['addr'])
      if (L.aax & L.iix):
        elapsed_time = int((time.perf_counter() - start_time) * 1000)
        L.EM_relay[2020:2020+len(helper.int32_to_uint16s(elapsed_time))] = helper.int32_to_uint16s(elapsed_time)


      #;Process:procedures_defnoreturn@49
      L.LD(L.local_MR['seq_step[6]']['name'], L.local_MR['seq_step[6]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[46]']['name'], L.local_MR['seq_step_reset1[46]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1046]']['name'], L.local_MR['seq_step[1046]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[46]']['name'], L.local_MR['seq_step[46]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.ANPB(L.local_MR['seq_step[46]']['name'], L.local_MR['seq_step[46]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1046]']['name'], L.local_MR['seq_step[1046]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1046]']['name'], L.local_MR['seq_step[1046]']['addr'])
      #;Post-Process:procedures_defnoreturn@49

      #;Process:moveP@50
      L.LD(L.local_MR['seq_step[1046]']['name'], L.local_MR['seq_step[1046]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[47]']['name'], L.local_MR['seq_step_reset1[47]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1047]']['name'], L.local_MR['seq_step[1047]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[47]']['name'], L.local_MR['seq_step[47]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[47]']['name'], L.local_T['move_static_timer[47]']['addr'])
      L.ANPB(L.local_MR['seq_step[47]']['name'], L.local_MR['seq_step[47]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1047]']['name'], L.local_MR['seq_step[1047]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1047]']['name'], L.local_MR['seq_step[1047]']['addr'])
      #;Post-Process:moveP@50
      #;timeout:moveP@50
      L.LD(L.local_MR['seq_step[47]']['name'], L.local_MR['seq_step[47]']['addr'])
      L.TMS(L.local_T['block_timeout[47]']['addr'], 60000000)
      L.LDP(L.local_T['block_timeout[47]']['name'], L.local_T['block_timeout[47]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+47, message='moveP@50:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+47, error_yaml=error_yaml)
      #;error:moveP@50
      L.LD(L.local_MR['seq_step[47]']['name'], L.local_MR['seq_step[47]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+47, message=f"moveP@50:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+47, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+47, message='moveP@50:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+47, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+47, message='moveP@50:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+47, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@50
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[47]']['name'], L.local_MR['seq_step[47]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[46]']['name'], L.local_MR['seq_step_reset1[46]']['addr'])
      L.LDP(L.local_MR['seq_step[47]']['name'], L.local_MR['seq_step[47]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool, posture = L.FB_setRobotParam(227.146, -10.351, 62.285, 0.0, 0.0, -32.643, 100.0, 100.0, 100.0, 0.1, 0.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, 60, program_override)
        RAC.send_command(f'moveAbsolutePtp({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {json.dumps({'TOOL': 1, 'USER': 1, 'POSTURE': posture, 'VEL': vel, 'ACC': acc, 'DEC': dec})})')
      L.LD(L.local_MR['seq_step[47]']['name'], L.local_MR['seq_step[47]']['addr'])
      L.ANB(L.local_MR['seq_step[1047]']['name'], L.local_MR['seq_step[1047]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {dist})')
      L.LD(L.local_MR['seq_step[47]']['name'], L.local_MR['seq_step[47]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[47]']['addr'], 0.0)
      L.LD(L.local_MR['seq_step[47]']['name'], L.local_MR['seq_step[47]']['addr'])
      L.OUT(L.local_MR['robot_busy[47]']['name'], L.local_MR['robot_busy[47]']['addr'])

      #;Process:moveP@51
      L.LD(L.local_MR['seq_step[1047]']['name'], L.local_MR['seq_step[1047]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[48]']['name'], L.local_MR['seq_step_reset1[48]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1048]']['name'], L.local_MR['seq_step[1048]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[48]']['name'], L.local_MR['seq_step[48]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[48]']['name'], L.local_T['move_static_timer[48]']['addr'])
      L.ANPB(L.local_MR['seq_step[48]']['name'], L.local_MR['seq_step[48]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1048]']['name'], L.local_MR['seq_step[1048]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1048]']['name'], L.local_MR['seq_step[1048]']['addr'])
      #;Post-Process:moveP@51
      #;timeout:moveP@51
      L.LD(L.local_MR['seq_step[48]']['name'], L.local_MR['seq_step[48]']['addr'])
      L.TMS(L.local_T['block_timeout[48]']['addr'], 60000000)
      L.LDP(L.local_T['block_timeout[48]']['name'], L.local_T['block_timeout[48]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+48, message='moveP@51:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+48, error_yaml=error_yaml)
      #;error:moveP@51
      L.LD(L.local_MR['seq_step[48]']['name'], L.local_MR['seq_step[48]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+48, message=f"moveP@51:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+48, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+48, message='moveP@51:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+48, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+48, message='moveP@51:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+48, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@51
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[48]']['name'], L.local_MR['seq_step[48]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[47]']['name'], L.local_MR['seq_step_reset1[47]']['addr'])
      L.LDP(L.local_MR['seq_step[48]']['name'], L.local_MR['seq_step[48]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool, posture = L.FB_setRobotParam(227.146, -10.351, 62.285, 0.0, 0.0, -32.643, 100.0, 100.0, 100.0, 0.1, 0.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, 60, program_override)
        RAC.send_command(f'moveAbsolutePtp({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {json.dumps({'TOOL': 1, 'USER': 1, 'POSTURE': posture, 'VEL': vel, 'ACC': acc, 'DEC': dec})})')
      L.LD(L.local_MR['seq_step[48]']['name'], L.local_MR['seq_step[48]']['addr'])
      L.ANB(L.local_MR['seq_step[1048]']['name'], L.local_MR['seq_step[1048]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {dist})')
      L.LD(L.local_MR['seq_step[48]']['name'], L.local_MR['seq_step[48]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[48]']['addr'], 0.0)
      L.LD(L.local_MR['seq_step[48]']['name'], L.local_MR['seq_step[48]']['addr'])
      L.OUT(L.local_MR['robot_busy[48]']['name'], L.local_MR['robot_busy[48]']['addr'])

      #;Process:procedures_callnoreturn@52
      L.LD(L.local_MR['seq_step[1048]']['name'], L.local_MR['seq_step[1048]']['addr'])
      L.MPS()
      L.LDB(L.local_MR['seq_step[1049]']['name'], L.local_MR['seq_step[1049]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[49]']['name'], L.local_MR['seq_step[49]']['addr'])
      L.MPP()
      L.LD(L.local_MR['seq_step[1030]']['name'], L.local_MR['seq_step[1030]']['addr'])
      L.ANPB(L.local_MR['seq_step[49]']['name'], L.local_MR['seq_step[49]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1049]']['name'], L.local_MR['seq_step[1049]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1049]']['name'], L.local_MR['seq_step[1049]']['addr'])
      #;Post-Process:procedures_callnoreturn@52
      #;action:procedures_callnoreturn@52
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[49]']['name'], L.local_MR['seq_step[49]']['addr'])
      L.AND(L.local_MR['seq_step[26]']['name'], L.local_MR['seq_step[26]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[48]']['name'], L.local_MR['seq_step_reset1[48]']['addr'])

      #;Process:set_speed@53
      L.LD(L.local_MR['seq_step[1049]']['name'], L.local_MR['seq_step[1049]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[50]']['name'], L.local_MR['seq_step_reset1[50]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1050]']['name'], L.local_MR['seq_step[1050]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[50]']['name'], L.local_MR['seq_step[50]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.ANPB(L.local_MR['seq_step[50]']['name'], L.local_MR['seq_step[50]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1050]']['name'], L.local_MR['seq_step[1050]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1050]']['name'], L.local_MR['seq_step[1050]']['addr'])
      #;Post-Process:set_speed@53
      #;action:set_speed@53
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[50]']['name'], L.local_MR['seq_step[50]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[49]']['name'], L.local_MR['seq_step_reset1[49]']['addr'])
      L.LDP(L.local_MR['seq_step[50]']['name'], L.local_MR['seq_step[50]']['addr'])
      if (L.aax & L.iix):
        program_override = 100

      #;Process:moveP@54
      L.LD(L.local_MR['seq_step[1050]']['name'], L.local_MR['seq_step[1050]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[51]']['name'], L.local_MR['seq_step_reset1[51]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1051]']['name'], L.local_MR['seq_step[1051]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[51]']['name'], L.local_MR['seq_step[51]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[51]']['name'], L.local_T['move_static_timer[51]']['addr'])
      L.ANPB(L.local_MR['seq_step[51]']['name'], L.local_MR['seq_step[51]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1051]']['name'], L.local_MR['seq_step[1051]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1051]']['name'], L.local_MR['seq_step[1051]']['addr'])
      #;Post-Process:moveP@54
      #;timeout:moveP@54
      L.LD(L.local_MR['seq_step[51]']['name'], L.local_MR['seq_step[51]']['addr'])
      L.TMS(L.local_T['block_timeout[51]']['addr'], 60000000)
      L.LDP(L.local_T['block_timeout[51]']['name'], L.local_T['block_timeout[51]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+51, message='moveP@54:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+51, error_yaml=error_yaml)
      #;error:moveP@54
      L.LD(L.local_MR['seq_step[51]']['name'], L.local_MR['seq_step[51]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+51, message=f"moveP@54:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+51, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+51, message='moveP@54:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+51, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+51, message='moveP@54:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+51, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@54
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[51]']['name'], L.local_MR['seq_step[51]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[50]']['name'], L.local_MR['seq_step_reset1[50]']['addr'])
      L.LDP(L.local_MR['seq_step[51]']['name'], L.local_MR['seq_step[51]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool, posture = L.FB_setRobotParam(227.146, -10.351, 62.285, 0.0, 0.0, -32.643, 100.0, 100.0, 100.0, 0.1, 0.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, 60, program_override)
        RAC.send_command(f'moveAbsolutePtp({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {json.dumps({'TOOL': 1, 'USER': 1, 'POSTURE': posture, 'VEL': vel, 'ACC': acc, 'DEC': dec})})')
      L.LD(L.local_MR['seq_step[51]']['name'], L.local_MR['seq_step[51]']['addr'])
      L.ANB(L.local_MR['seq_step[1051]']['name'], L.local_MR['seq_step[1051]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {dist})')
      L.LD(L.local_MR['seq_step[51]']['name'], L.local_MR['seq_step[51]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[51]']['addr'], 0.0)
      L.LD(L.local_MR['seq_step[51]']['name'], L.local_MR['seq_step[51]']['addr'])
      L.OUT(L.local_MR['robot_busy[51]']['name'], L.local_MR['robot_busy[51]']['addr'])

      #;Process:procedures_callnoreturn@55
      L.LD(L.local_MR['seq_step[1051]']['name'], L.local_MR['seq_step[1051]']['addr'])
      L.MPS()
      L.LDB(L.local_MR['seq_step[1052]']['name'], L.local_MR['seq_step[1052]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[52]']['name'], L.local_MR['seq_step[52]']['addr'])
      L.MPP()
      L.LD(L.local_MR['seq_step[1035]']['name'], L.local_MR['seq_step[1035]']['addr'])
      L.ANPB(L.local_MR['seq_step[52]']['name'], L.local_MR['seq_step[52]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1052]']['name'], L.local_MR['seq_step[1052]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1052]']['name'], L.local_MR['seq_step[1052]']['addr'])
      #;Post-Process:procedures_callnoreturn@55
      #;action:procedures_callnoreturn@55
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[52]']['name'], L.local_MR['seq_step[52]']['addr'])
      L.AND(L.local_MR['seq_step[31]']['name'], L.local_MR['seq_step[31]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[51]']['name'], L.local_MR['seq_step_reset1[51]']['addr'])

      #;Process:set_speed@56
      L.LD(L.local_MR['seq_step[1052]']['name'], L.local_MR['seq_step[1052]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[53]']['name'], L.local_MR['seq_step_reset1[53]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1053]']['name'], L.local_MR['seq_step[1053]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[53]']['name'], L.local_MR['seq_step[53]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.ANPB(L.local_MR['seq_step[53]']['name'], L.local_MR['seq_step[53]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1053]']['name'], L.local_MR['seq_step[1053]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1053]']['name'], L.local_MR['seq_step[1053]']['addr'])
      #;Post-Process:set_speed@56
      #;action:set_speed@56
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[53]']['name'], L.local_MR['seq_step[53]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[52]']['name'], L.local_MR['seq_step_reset1[52]']['addr'])
      L.LDP(L.local_MR['seq_step[53]']['name'], L.local_MR['seq_step[53]']['addr'])
      if (L.aax & L.iix):
        program_override = 100

      #;Process:moveP@57
      L.LD(L.local_MR['seq_step[1053]']['name'], L.local_MR['seq_step[1053]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[54]']['name'], L.local_MR['seq_step_reset1[54]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1054]']['name'], L.local_MR['seq_step[1054]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[54]']['name'], L.local_MR['seq_step[54]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[54]']['name'], L.local_T['move_static_timer[54]']['addr'])
      L.ANPB(L.local_MR['seq_step[54]']['name'], L.local_MR['seq_step[54]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1054]']['name'], L.local_MR['seq_step[1054]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1054]']['name'], L.local_MR['seq_step[1054]']['addr'])
      #;Post-Process:moveP@57
      #;timeout:moveP@57
      L.LD(L.local_MR['seq_step[54]']['name'], L.local_MR['seq_step[54]']['addr'])
      L.TMS(L.local_T['block_timeout[54]']['addr'], 60000000)
      L.LDP(L.local_T['block_timeout[54]']['name'], L.local_T['block_timeout[54]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+54, message='moveP@57:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+54, error_yaml=error_yaml)
      #;error:moveP@57
      L.LD(L.local_MR['seq_step[54]']['name'], L.local_MR['seq_step[54]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+54, message=f"moveP@57:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+54, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+54, message='moveP@57:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+54, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+54, message='moveP@57:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+54, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@57
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[54]']['name'], L.local_MR['seq_step[54]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[53]']['name'], L.local_MR['seq_step_reset1[53]']['addr'])
      L.LDP(L.local_MR['seq_step[54]']['name'], L.local_MR['seq_step[54]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool, posture = L.FB_setRobotParam(227.146, -10.351, 62.285, 0.0, 0.0, -32.643, 100.0, 100.0, 100.0, 0.1, 0.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, 60, program_override)
        RAC.send_command(f'moveAbsolutePtp({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {json.dumps({'TOOL': 1, 'USER': 1, 'POSTURE': posture, 'VEL': vel, 'ACC': acc, 'DEC': dec})})')
      L.LD(L.local_MR['seq_step[54]']['name'], L.local_MR['seq_step[54]']['addr'])
      L.ANB(L.local_MR['seq_step[1054]']['name'], L.local_MR['seq_step[1054]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {dist})')
      L.LD(L.local_MR['seq_step[54]']['name'], L.local_MR['seq_step[54]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[54]']['addr'], 0.0)
      L.LD(L.local_MR['seq_step[54]']['name'], L.local_MR['seq_step[54]']['addr'])
      L.OUT(L.local_MR['robot_busy[54]']['name'], L.local_MR['robot_busy[54]']['addr'])

      #;Process:moveP@58
      L.LD(L.local_MR['seq_step[1054]']['name'], L.local_MR['seq_step[1054]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[55]']['name'], L.local_MR['seq_step_reset1[55]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1055]']['name'], L.local_MR['seq_step[1055]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[55]']['name'], L.local_MR['seq_step[55]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[55]']['name'], L.local_T['move_static_timer[55]']['addr'])
      L.ANPB(L.local_MR['seq_step[55]']['name'], L.local_MR['seq_step[55]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1055]']['name'], L.local_MR['seq_step[1055]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1055]']['name'], L.local_MR['seq_step[1055]']['addr'])
      #;Post-Process:moveP@58
      #;timeout:moveP@58
      L.LD(L.local_MR['seq_step[55]']['name'], L.local_MR['seq_step[55]']['addr'])
      L.TMS(L.local_T['block_timeout[55]']['addr'], 60000000)
      L.LDP(L.local_T['block_timeout[55]']['name'], L.local_T['block_timeout[55]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+55, message='moveP@58:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+55, error_yaml=error_yaml)
      #;error:moveP@58
      L.LD(L.local_MR['seq_step[55]']['name'], L.local_MR['seq_step[55]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+55, message=f"moveP@58:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+55, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+55, message='moveP@58:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+55, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+55, message='moveP@58:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+55, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@58
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[55]']['name'], L.local_MR['seq_step[55]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[54]']['name'], L.local_MR['seq_step_reset1[54]']['addr'])
      L.LDP(L.local_MR['seq_step[55]']['name'], L.local_MR['seq_step[55]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool, posture = L.FB_setRobotParam(227.146, -10.351, 62.285, 0.0, 0.0, -32.643, 100.0, 100.0, 100.0, 0.1, 0.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, 60, program_override)
        RAC.send_command(f'moveAbsolutePtp({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {json.dumps({'TOOL': 1, 'USER': 1, 'POSTURE': posture, 'VEL': vel, 'ACC': acc, 'DEC': dec})})')
      L.LD(L.local_MR['seq_step[55]']['name'], L.local_MR['seq_step[55]']['addr'])
      L.ANB(L.local_MR['seq_step[1055]']['name'], L.local_MR['seq_step[1055]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {dist})')
      L.LD(L.local_MR['seq_step[55]']['name'], L.local_MR['seq_step[55]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[55]']['addr'], 0.0)
      L.LD(L.local_MR['seq_step[55]']['name'], L.local_MR['seq_step[55]']['addr'])
      L.OUT(L.local_MR['robot_busy[55]']['name'], L.local_MR['robot_busy[55]']['addr'])

      #;Process:return@59
      L.LD(L.local_MR['seq_step[1055]']['name'], L.local_MR['seq_step[1055]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[56]']['name'], L.local_MR['seq_step_reset1[56]']['addr'])
      L.MPS()
      L.ANB(L.local_MR['seq_step[1056]']['name'], L.local_MR['seq_step[1056]']['addr'])
      L.OUT(L.local_MR['seq_step[56]']['name'], L.local_MR['seq_step[56]']['addr'])
      L.MPP()
      L.LDPB(L.local_MR['seq_step[56]']['name'], L.local_MR['seq_step[56]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1056]']['name'], L.local_MR['seq_step[1056]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1056]']['name'], L.local_MR['seq_step[1056]']['addr'])
      #;Post-Process:return@59
      #;action:return@59
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[56]']['name'], L.local_MR['seq_step[56]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[55]']['name'], L.local_MR['seq_step_reset1[55]']['addr'])
      L.LDP(L.local_MR['seq_step[56]']['name'], L.local_MR['seq_step[56]']['addr'])
      if (L.aax & L.iix):
        elapsed_time = int((time.perf_counter() - start_time) * 1000)
        L.EM_relay[2020:2020+len(helper.int32_to_uint16s(elapsed_time))] = helper.int32_to_uint16s(elapsed_time)


      #;Process:procedures_defnoreturn@60
      L.LD(L.local_MR['seq_step[7]']['name'], L.local_MR['seq_step[7]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[57]']['name'], L.local_MR['seq_step_reset1[57]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1057]']['name'], L.local_MR['seq_step[1057]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[57]']['name'], L.local_MR['seq_step[57]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.ANPB(L.local_MR['seq_step[57]']['name'], L.local_MR['seq_step[57]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1057]']['name'], L.local_MR['seq_step[1057]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1057]']['name'], L.local_MR['seq_step[1057]']['addr'])
      #;Post-Process:procedures_defnoreturn@60

      #;Process:moveP@61
      L.LD(L.local_MR['seq_step[1057]']['name'], L.local_MR['seq_step[1057]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[58]']['name'], L.local_MR['seq_step_reset1[58]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1058]']['name'], L.local_MR['seq_step[1058]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[58]']['name'], L.local_MR['seq_step[58]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[58]']['name'], L.local_T['move_static_timer[58]']['addr'])
      L.ANPB(L.local_MR['seq_step[58]']['name'], L.local_MR['seq_step[58]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1058]']['name'], L.local_MR['seq_step[1058]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1058]']['name'], L.local_MR['seq_step[1058]']['addr'])
      #;Post-Process:moveP@61
      #;timeout:moveP@61
      L.LD(L.local_MR['seq_step[58]']['name'], L.local_MR['seq_step[58]']['addr'])
      L.TMS(L.local_T['block_timeout[58]']['addr'], 60000000)
      L.LDP(L.local_T['block_timeout[58]']['name'], L.local_T['block_timeout[58]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+58, message='moveP@61:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+58, error_yaml=error_yaml)
      #;error:moveP@61
      L.LD(L.local_MR['seq_step[58]']['name'], L.local_MR['seq_step[58]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+58, message=f"moveP@61:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+58, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+58, message='moveP@61:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+58, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+58, message='moveP@61:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+58, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@61
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[58]']['name'], L.local_MR['seq_step[58]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[57]']['name'], L.local_MR['seq_step_reset1[57]']['addr'])
      L.LDP(L.local_MR['seq_step[58]']['name'], L.local_MR['seq_step[58]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool, posture = L.FB_setRobotParam(227.146, -10.351, 62.285, 0.0, 0.0, -32.643, 100.0, 100.0, 100.0, 0.1, 0.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, 60, program_override)
        RAC.send_command(f'moveAbsolutePtp({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {json.dumps({'TOOL': 1, 'USER': 1, 'POSTURE': posture, 'VEL': vel, 'ACC': acc, 'DEC': dec})})')
      L.LD(L.local_MR['seq_step[58]']['name'], L.local_MR['seq_step[58]']['addr'])
      L.ANB(L.local_MR['seq_step[1058]']['name'], L.local_MR['seq_step[1058]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {dist})')
      L.LD(L.local_MR['seq_step[58]']['name'], L.local_MR['seq_step[58]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[58]']['addr'], 0.0)
      L.LD(L.local_MR['seq_step[58]']['name'], L.local_MR['seq_step[58]']['addr'])
      L.OUT(L.local_MR['robot_busy[58]']['name'], L.local_MR['robot_busy[58]']['addr'])

      #;Process:moveP@62
      L.LD(L.local_MR['seq_step[1058]']['name'], L.local_MR['seq_step[1058]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[59]']['name'], L.local_MR['seq_step_reset1[59]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1059]']['name'], L.local_MR['seq_step[1059]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[59]']['name'], L.local_MR['seq_step[59]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[59]']['name'], L.local_T['move_static_timer[59]']['addr'])
      L.ANPB(L.local_MR['seq_step[59]']['name'], L.local_MR['seq_step[59]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1059]']['name'], L.local_MR['seq_step[1059]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1059]']['name'], L.local_MR['seq_step[1059]']['addr'])
      #;Post-Process:moveP@62
      #;timeout:moveP@62
      L.LD(L.local_MR['seq_step[59]']['name'], L.local_MR['seq_step[59]']['addr'])
      L.TMS(L.local_T['block_timeout[59]']['addr'], 60000000)
      L.LDP(L.local_T['block_timeout[59]']['name'], L.local_T['block_timeout[59]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+59, message='moveP@62:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+59, error_yaml=error_yaml)
      #;error:moveP@62
      L.LD(L.local_MR['seq_step[59]']['name'], L.local_MR['seq_step[59]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+59, message=f"moveP@62:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+59, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+59, message='moveP@62:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+59, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+59, message='moveP@62:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+59, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@62
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[59]']['name'], L.local_MR['seq_step[59]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[58]']['name'], L.local_MR['seq_step_reset1[58]']['addr'])
      L.LDP(L.local_MR['seq_step[59]']['name'], L.local_MR['seq_step[59]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool, posture = L.FB_setRobotParam(227.146, -10.351, 62.285, 0.0, 0.0, -32.643, 100.0, 100.0, 100.0, 0.1, 0.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, 60, program_override)
        RAC.send_command(f'moveAbsolutePtp({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {json.dumps({'TOOL': 1, 'USER': 1, 'POSTURE': posture, 'VEL': vel, 'ACC': acc, 'DEC': dec})})')
      L.LD(L.local_MR['seq_step[59]']['name'], L.local_MR['seq_step[59]']['addr'])
      L.ANB(L.local_MR['seq_step[1059]']['name'], L.local_MR['seq_step[1059]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {dist})')
      L.LD(L.local_MR['seq_step[59]']['name'], L.local_MR['seq_step[59]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[59]']['addr'], 0.0)
      L.LD(L.local_MR['seq_step[59]']['name'], L.local_MR['seq_step[59]']['addr'])
      L.OUT(L.local_MR['robot_busy[59]']['name'], L.local_MR['robot_busy[59]']['addr'])

      #;Process:procedures_callnoreturn@63
      L.LD(L.local_MR['seq_step[1059]']['name'], L.local_MR['seq_step[1059]']['addr'])
      L.MPS()
      L.LDB(L.local_MR['seq_step[1060]']['name'], L.local_MR['seq_step[1060]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[60]']['name'], L.local_MR['seq_step[60]']['addr'])
      L.MPP()
      L.LD(L.local_MR['seq_step[1040]']['name'], L.local_MR['seq_step[1040]']['addr'])
      L.ANPB(L.local_MR['seq_step[60]']['name'], L.local_MR['seq_step[60]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1060]']['name'], L.local_MR['seq_step[1060]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1060]']['name'], L.local_MR['seq_step[1060]']['addr'])
      #;Post-Process:procedures_callnoreturn@63
      #;action:procedures_callnoreturn@63
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[60]']['name'], L.local_MR['seq_step[60]']['addr'])
      L.AND(L.local_MR['seq_step[36]']['name'], L.local_MR['seq_step[36]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[59]']['name'], L.local_MR['seq_step_reset1[59]']['addr'])

      #;Process:set_speed@64
      L.LD(L.local_MR['seq_step[1060]']['name'], L.local_MR['seq_step[1060]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[61]']['name'], L.local_MR['seq_step_reset1[61]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1061]']['name'], L.local_MR['seq_step[1061]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[61]']['name'], L.local_MR['seq_step[61]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.ANPB(L.local_MR['seq_step[61]']['name'], L.local_MR['seq_step[61]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1061]']['name'], L.local_MR['seq_step[1061]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1061]']['name'], L.local_MR['seq_step[1061]']['addr'])
      #;Post-Process:set_speed@64
      #;action:set_speed@64
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[61]']['name'], L.local_MR['seq_step[61]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[60]']['name'], L.local_MR['seq_step_reset1[60]']['addr'])
      L.LDP(L.local_MR['seq_step[61]']['name'], L.local_MR['seq_step[61]']['addr'])
      if (L.aax & L.iix):
        program_override = 100

      #;Process:moveP@65
      L.LD(L.local_MR['seq_step[1061]']['name'], L.local_MR['seq_step[1061]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[62]']['name'], L.local_MR['seq_step_reset1[62]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1062]']['name'], L.local_MR['seq_step[1062]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[62]']['name'], L.local_MR['seq_step[62]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[62]']['name'], L.local_T['move_static_timer[62]']['addr'])
      L.ANPB(L.local_MR['seq_step[62]']['name'], L.local_MR['seq_step[62]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1062]']['name'], L.local_MR['seq_step[1062]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1062]']['name'], L.local_MR['seq_step[1062]']['addr'])
      #;Post-Process:moveP@65
      #;timeout:moveP@65
      L.LD(L.local_MR['seq_step[62]']['name'], L.local_MR['seq_step[62]']['addr'])
      L.TMS(L.local_T['block_timeout[62]']['addr'], 60000000)
      L.LDP(L.local_T['block_timeout[62]']['name'], L.local_T['block_timeout[62]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+62, message='moveP@65:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+62, error_yaml=error_yaml)
      #;error:moveP@65
      L.LD(L.local_MR['seq_step[62]']['name'], L.local_MR['seq_step[62]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+62, message=f"moveP@65:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+62, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+62, message='moveP@65:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+62, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+62, message='moveP@65:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+62, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@65
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[62]']['name'], L.local_MR['seq_step[62]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[61]']['name'], L.local_MR['seq_step_reset1[61]']['addr'])
      L.LDP(L.local_MR['seq_step[62]']['name'], L.local_MR['seq_step[62]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool, posture = L.FB_setRobotParam(227.146, -10.351, 62.285, 0.0, 0.0, -32.643, 100.0, 100.0, 100.0, 0.1, 0.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, 60, program_override)
        RAC.send_command(f'moveAbsolutePtp({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {json.dumps({'TOOL': 1, 'USER': 1, 'POSTURE': posture, 'VEL': vel, 'ACC': acc, 'DEC': dec})})')
      L.LD(L.local_MR['seq_step[62]']['name'], L.local_MR['seq_step[62]']['addr'])
      L.ANB(L.local_MR['seq_step[1062]']['name'], L.local_MR['seq_step[1062]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {dist})')
      L.LD(L.local_MR['seq_step[62]']['name'], L.local_MR['seq_step[62]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[62]']['addr'], 0.0)
      L.LD(L.local_MR['seq_step[62]']['name'], L.local_MR['seq_step[62]']['addr'])
      L.OUT(L.local_MR['robot_busy[62]']['name'], L.local_MR['robot_busy[62]']['addr'])

      #;Process:procedures_callnoreturn@66
      L.LD(L.local_MR['seq_step[1062]']['name'], L.local_MR['seq_step[1062]']['addr'])
      L.MPS()
      L.LDB(L.local_MR['seq_step[1063]']['name'], L.local_MR['seq_step[1063]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[63]']['name'], L.local_MR['seq_step[63]']['addr'])
      L.MPP()
      L.LD(L.local_MR['seq_step[1045]']['name'], L.local_MR['seq_step[1045]']['addr'])
      L.ANPB(L.local_MR['seq_step[63]']['name'], L.local_MR['seq_step[63]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1063]']['name'], L.local_MR['seq_step[1063]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1063]']['name'], L.local_MR['seq_step[1063]']['addr'])
      #;Post-Process:procedures_callnoreturn@66
      #;action:procedures_callnoreturn@66
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[63]']['name'], L.local_MR['seq_step[63]']['addr'])
      L.AND(L.local_MR['seq_step[41]']['name'], L.local_MR['seq_step[41]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[62]']['name'], L.local_MR['seq_step_reset1[62]']['addr'])

      #;Process:set_speed@67
      L.LD(L.local_MR['seq_step[1063]']['name'], L.local_MR['seq_step[1063]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[64]']['name'], L.local_MR['seq_step_reset1[64]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1064]']['name'], L.local_MR['seq_step[1064]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[64]']['name'], L.local_MR['seq_step[64]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.ANPB(L.local_MR['seq_step[64]']['name'], L.local_MR['seq_step[64]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1064]']['name'], L.local_MR['seq_step[1064]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1064]']['name'], L.local_MR['seq_step[1064]']['addr'])
      #;Post-Process:set_speed@67
      #;action:set_speed@67
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[64]']['name'], L.local_MR['seq_step[64]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[63]']['name'], L.local_MR['seq_step_reset1[63]']['addr'])
      L.LDP(L.local_MR['seq_step[64]']['name'], L.local_MR['seq_step[64]']['addr'])
      if (L.aax & L.iix):
        program_override = 100

      #;Process:moveP@68
      L.LD(L.local_MR['seq_step[1064]']['name'], L.local_MR['seq_step[1064]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[65]']['name'], L.local_MR['seq_step_reset1[65]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1065]']['name'], L.local_MR['seq_step[1065]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[65]']['name'], L.local_MR['seq_step[65]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[65]']['name'], L.local_T['move_static_timer[65]']['addr'])
      L.ANPB(L.local_MR['seq_step[65]']['name'], L.local_MR['seq_step[65]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1065]']['name'], L.local_MR['seq_step[1065]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1065]']['name'], L.local_MR['seq_step[1065]']['addr'])
      #;Post-Process:moveP@68
      #;timeout:moveP@68
      L.LD(L.local_MR['seq_step[65]']['name'], L.local_MR['seq_step[65]']['addr'])
      L.TMS(L.local_T['block_timeout[65]']['addr'], 60000000)
      L.LDP(L.local_T['block_timeout[65]']['name'], L.local_T['block_timeout[65]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+65, message='moveP@68:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+65, error_yaml=error_yaml)
      #;error:moveP@68
      L.LD(L.local_MR['seq_step[65]']['name'], L.local_MR['seq_step[65]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+65, message=f"moveP@68:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+65, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+65, message='moveP@68:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+65, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+65, message='moveP@68:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+65, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@68
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[65]']['name'], L.local_MR['seq_step[65]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[64]']['name'], L.local_MR['seq_step_reset1[64]']['addr'])
      L.LDP(L.local_MR['seq_step[65]']['name'], L.local_MR['seq_step[65]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool, posture = L.FB_setRobotParam(227.146, -10.351, 62.285, 0.0, 0.0, -32.643, 100.0, 100.0, 100.0, 0.1, 0.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, 60, program_override)
        RAC.send_command(f'moveAbsolutePtp({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {json.dumps({'TOOL': 1, 'USER': 1, 'POSTURE': posture, 'VEL': vel, 'ACC': acc, 'DEC': dec})})')
      L.LD(L.local_MR['seq_step[65]']['name'], L.local_MR['seq_step[65]']['addr'])
      L.ANB(L.local_MR['seq_step[1065]']['name'], L.local_MR['seq_step[1065]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {dist})')
      L.LD(L.local_MR['seq_step[65]']['name'], L.local_MR['seq_step[65]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[65]']['addr'], 0.0)
      L.LD(L.local_MR['seq_step[65]']['name'], L.local_MR['seq_step[65]']['addr'])
      L.OUT(L.local_MR['robot_busy[65]']['name'], L.local_MR['robot_busy[65]']['addr'])

      #;Process:moveP@69
      L.LD(L.local_MR['seq_step[1065]']['name'], L.local_MR['seq_step[1065]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[66]']['name'], L.local_MR['seq_step_reset1[66]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1066]']['name'], L.local_MR['seq_step[1066]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[66]']['name'], L.local_MR['seq_step[66]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[66]']['name'], L.local_T['move_static_timer[66]']['addr'])
      L.ANPB(L.local_MR['seq_step[66]']['name'], L.local_MR['seq_step[66]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1066]']['name'], L.local_MR['seq_step[1066]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1066]']['name'], L.local_MR['seq_step[1066]']['addr'])
      #;Post-Process:moveP@69
      #;timeout:moveP@69
      L.LD(L.local_MR['seq_step[66]']['name'], L.local_MR['seq_step[66]']['addr'])
      L.TMS(L.local_T['block_timeout[66]']['addr'], 60000000)
      L.LDP(L.local_T['block_timeout[66]']['name'], L.local_T['block_timeout[66]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+66, message='moveP@69:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+66, error_yaml=error_yaml)
      #;error:moveP@69
      L.LD(L.local_MR['seq_step[66]']['name'], L.local_MR['seq_step[66]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+66, message=f"moveP@69:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+66, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+66, message='moveP@69:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+66, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+66, message='moveP@69:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+66, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@69
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[66]']['name'], L.local_MR['seq_step[66]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[65]']['name'], L.local_MR['seq_step_reset1[65]']['addr'])
      L.LDP(L.local_MR['seq_step[66]']['name'], L.local_MR['seq_step[66]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool, posture = L.FB_setRobotParam(227.146, -10.351, 62.285, 0.0, 0.0, -32.643, 100.0, 100.0, 100.0, 0.1, 0.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, 60, program_override)
        RAC.send_command(f'moveAbsolutePtp({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {json.dumps({'TOOL': 1, 'USER': 1, 'POSTURE': posture, 'VEL': vel, 'ACC': acc, 'DEC': dec})})')
      L.LD(L.local_MR['seq_step[66]']['name'], L.local_MR['seq_step[66]']['addr'])
      L.ANB(L.local_MR['seq_step[1066]']['name'], L.local_MR['seq_step[1066]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {dist})')
      L.LD(L.local_MR['seq_step[66]']['name'], L.local_MR['seq_step[66]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[66]']['addr'], 0.0)
      L.LD(L.local_MR['seq_step[66]']['name'], L.local_MR['seq_step[66]']['addr'])
      L.OUT(L.local_MR['robot_busy[66]']['name'], L.local_MR['robot_busy[66]']['addr'])

      #;Process:return@70
      L.LD(L.local_MR['seq_step[1066]']['name'], L.local_MR['seq_step[1066]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[67]']['name'], L.local_MR['seq_step_reset1[67]']['addr'])
      L.MPS()
      L.ANB(L.local_MR['seq_step[1067]']['name'], L.local_MR['seq_step[1067]']['addr'])
      L.OUT(L.local_MR['seq_step[67]']['name'], L.local_MR['seq_step[67]']['addr'])
      L.MPP()
      L.LDPB(L.local_MR['seq_step[67]']['name'], L.local_MR['seq_step[67]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1067]']['name'], L.local_MR['seq_step[1067]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1067]']['name'], L.local_MR['seq_step[1067]']['addr'])
      #;Post-Process:return@70
      #;action:return@70
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[67]']['name'], L.local_MR['seq_step[67]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[66]']['name'], L.local_MR['seq_step_reset1[66]']['addr'])
      L.LDP(L.local_MR['seq_step[67]']['name'], L.local_MR['seq_step[67]']['addr'])
      if (L.aax & L.iix):
        elapsed_time = int((time.perf_counter() - start_time) * 1000)
        L.EM_relay[2020:2020+len(helper.int32_to_uint16s(elapsed_time))] = helper.int32_to_uint16s(elapsed_time)


      #;Process:procedures_defnoreturn@71
      L.LD(L.local_MR['seq_step[10]']['name'], L.local_MR['seq_step[10]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[68]']['name'], L.local_MR['seq_step_reset1[68]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1068]']['name'], L.local_MR['seq_step[1068]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[68]']['name'], L.local_MR['seq_step[68]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.ANPB(L.local_MR['seq_step[68]']['name'], L.local_MR['seq_step[68]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1068]']['name'], L.local_MR['seq_step[1068]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1068]']['name'], L.local_MR['seq_step[1068]']['addr'])
      #;Post-Process:procedures_defnoreturn@71

      #;Process:moveP@72
      L.LD(L.local_MR['seq_step[1068]']['name'], L.local_MR['seq_step[1068]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[69]']['name'], L.local_MR['seq_step_reset1[69]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1069]']['name'], L.local_MR['seq_step[1069]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[69]']['name'], L.local_MR['seq_step[69]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[69]']['name'], L.local_T['move_static_timer[69]']['addr'])
      L.ANPB(L.local_MR['seq_step[69]']['name'], L.local_MR['seq_step[69]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1069]']['name'], L.local_MR['seq_step[1069]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1069]']['name'], L.local_MR['seq_step[1069]']['addr'])
      #;Post-Process:moveP@72
      #;timeout:moveP@72
      L.LD(L.local_MR['seq_step[69]']['name'], L.local_MR['seq_step[69]']['addr'])
      L.TMS(L.local_T['block_timeout[69]']['addr'], 60000000)
      L.LDP(L.local_T['block_timeout[69]']['name'], L.local_T['block_timeout[69]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+69, message='moveP@72:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+69, error_yaml=error_yaml)
      #;error:moveP@72
      L.LD(L.local_MR['seq_step[69]']['name'], L.local_MR['seq_step[69]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+69, message=f"moveP@72:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+69, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+69, message='moveP@72:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+69, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+69, message='moveP@72:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+69, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@72
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[69]']['name'], L.local_MR['seq_step[69]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[68]']['name'], L.local_MR['seq_step_reset1[68]']['addr'])
      L.LDP(L.local_MR['seq_step[69]']['name'], L.local_MR['seq_step[69]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool, posture = L.FB_setRobotParam(227.146, -10.351, 62.285, 0.0, 0.0, -32.643, 100.0, 100.0, 100.0, 0.1, 0.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, 60, program_override)
        RAC.send_command(f'moveAbsolutePtp({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {json.dumps({'TOOL': 1, 'USER': 1, 'POSTURE': posture, 'VEL': vel, 'ACC': acc, 'DEC': dec})})')
      L.LD(L.local_MR['seq_step[69]']['name'], L.local_MR['seq_step[69]']['addr'])
      L.ANB(L.local_MR['seq_step[1069]']['name'], L.local_MR['seq_step[1069]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {dist})')
      L.LD(L.local_MR['seq_step[69]']['name'], L.local_MR['seq_step[69]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[69]']['addr'], 0.0)
      L.LD(L.local_MR['seq_step[69]']['name'], L.local_MR['seq_step[69]']['addr'])
      L.OUT(L.local_MR['robot_busy[69]']['name'], L.local_MR['robot_busy[69]']['addr'])

      #;Process:moveP@73
      L.LD(L.local_MR['seq_step[1069]']['name'], L.local_MR['seq_step[1069]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[70]']['name'], L.local_MR['seq_step_reset1[70]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1070]']['name'], L.local_MR['seq_step[1070]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[70]']['name'], L.local_MR['seq_step[70]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[70]']['name'], L.local_T['move_static_timer[70]']['addr'])
      L.ANPB(L.local_MR['seq_step[70]']['name'], L.local_MR['seq_step[70]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1070]']['name'], L.local_MR['seq_step[1070]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1070]']['name'], L.local_MR['seq_step[1070]']['addr'])
      #;Post-Process:moveP@73
      #;timeout:moveP@73
      L.LD(L.local_MR['seq_step[70]']['name'], L.local_MR['seq_step[70]']['addr'])
      L.TMS(L.local_T['block_timeout[70]']['addr'], 60000000)
      L.LDP(L.local_T['block_timeout[70]']['name'], L.local_T['block_timeout[70]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+70, message='moveP@73:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+70, error_yaml=error_yaml)
      #;error:moveP@73
      L.LD(L.local_MR['seq_step[70]']['name'], L.local_MR['seq_step[70]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+70, message=f"moveP@73:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+70, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+70, message='moveP@73:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+70, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+70, message='moveP@73:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+70, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@73
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[70]']['name'], L.local_MR['seq_step[70]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[69]']['name'], L.local_MR['seq_step_reset1[69]']['addr'])
      L.LDP(L.local_MR['seq_step[70]']['name'], L.local_MR['seq_step[70]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool, posture = L.FB_setRobotParam(227.146, -10.351, 62.285, 0.0, 0.0, -32.643, 100.0, 100.0, 100.0, 0.1, 0.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, 60, program_override)
        RAC.send_command(f'moveAbsolutePtp({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {json.dumps({'TOOL': 1, 'USER': 1, 'POSTURE': posture, 'VEL': vel, 'ACC': acc, 'DEC': dec})})')
      L.LD(L.local_MR['seq_step[70]']['name'], L.local_MR['seq_step[70]']['addr'])
      L.ANB(L.local_MR['seq_step[1070]']['name'], L.local_MR['seq_step[1070]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {dist})')
      L.LD(L.local_MR['seq_step[70]']['name'], L.local_MR['seq_step[70]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[70]']['addr'], 0.0)
      L.LD(L.local_MR['seq_step[70]']['name'], L.local_MR['seq_step[70]']['addr'])
      L.OUT(L.local_MR['robot_busy[70]']['name'], L.local_MR['robot_busy[70]']['addr'])

      #;Process:set_speed@74
      L.LD(L.local_MR['seq_step[1070]']['name'], L.local_MR['seq_step[1070]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[71]']['name'], L.local_MR['seq_step_reset1[71]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1071]']['name'], L.local_MR['seq_step[1071]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[71]']['name'], L.local_MR['seq_step[71]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.ANPB(L.local_MR['seq_step[71]']['name'], L.local_MR['seq_step[71]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1071]']['name'], L.local_MR['seq_step[1071]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1071]']['name'], L.local_MR['seq_step[1071]']['addr'])
      #;Post-Process:set_speed@74
      #;action:set_speed@74
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[71]']['name'], L.local_MR['seq_step[71]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[70]']['name'], L.local_MR['seq_step_reset1[70]']['addr'])
      L.LDP(L.local_MR['seq_step[71]']['name'], L.local_MR['seq_step[71]']['addr'])
      if (L.aax & L.iix):
        program_override = 100

      #;Process:moveP@75
      L.LD(L.local_MR['seq_step[1071]']['name'], L.local_MR['seq_step[1071]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[72]']['name'], L.local_MR['seq_step_reset1[72]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1072]']['name'], L.local_MR['seq_step[1072]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[72]']['name'], L.local_MR['seq_step[72]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[72]']['name'], L.local_T['move_static_timer[72]']['addr'])
      L.ANPB(L.local_MR['seq_step[72]']['name'], L.local_MR['seq_step[72]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1072]']['name'], L.local_MR['seq_step[1072]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1072]']['name'], L.local_MR['seq_step[1072]']['addr'])
      #;Post-Process:moveP@75
      #;timeout:moveP@75
      L.LD(L.local_MR['seq_step[72]']['name'], L.local_MR['seq_step[72]']['addr'])
      L.TMS(L.local_T['block_timeout[72]']['addr'], 60000000)
      L.LDP(L.local_T['block_timeout[72]']['name'], L.local_T['block_timeout[72]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+72, message='moveP@75:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+72, error_yaml=error_yaml)
      #;error:moveP@75
      L.LD(L.local_MR['seq_step[72]']['name'], L.local_MR['seq_step[72]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+72, message=f"moveP@75:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+72, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+72, message='moveP@75:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+72, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+72, message='moveP@75:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+72, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@75
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[72]']['name'], L.local_MR['seq_step[72]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[71]']['name'], L.local_MR['seq_step_reset1[71]']['addr'])
      L.LDP(L.local_MR['seq_step[72]']['name'], L.local_MR['seq_step[72]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool, posture = L.FB_setRobotParam(227.146, -10.351, 62.285, 0.0, 0.0, -32.643, 100.0, 100.0, 100.0, 0.1, 0.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, 60, program_override)
        RAC.send_command(f'moveAbsolutePtp({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {json.dumps({'TOOL': 1, 'USER': 1, 'POSTURE': posture, 'VEL': vel, 'ACC': acc, 'DEC': dec})})')
      L.LD(L.local_MR['seq_step[72]']['name'], L.local_MR['seq_step[72]']['addr'])
      L.ANB(L.local_MR['seq_step[1072]']['name'], L.local_MR['seq_step[1072]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {dist})')
      L.LD(L.local_MR['seq_step[72]']['name'], L.local_MR['seq_step[72]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[72]']['addr'], 0.0)
      L.LD(L.local_MR['seq_step[72]']['name'], L.local_MR['seq_step[72]']['addr'])
      L.OUT(L.local_MR['robot_busy[72]']['name'], L.local_MR['robot_busy[72]']['addr'])

      #;Process:procedures_callnoreturn@76
      L.LD(L.local_MR['seq_step[1072]']['name'], L.local_MR['seq_step[1072]']['addr'])
      L.MPS()
      L.LDB(L.local_MR['seq_step[1073]']['name'], L.local_MR['seq_step[1073]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[73]']['name'], L.local_MR['seq_step[73]']['addr'])
      L.MPP()
      L.LD(L.local_MR['seq_step[1040]']['name'], L.local_MR['seq_step[1040]']['addr'])
      L.ANPB(L.local_MR['seq_step[73]']['name'], L.local_MR['seq_step[73]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1073]']['name'], L.local_MR['seq_step[1073]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1073]']['name'], L.local_MR['seq_step[1073]']['addr'])
      #;Post-Process:procedures_callnoreturn@76
      #;action:procedures_callnoreturn@76
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[73]']['name'], L.local_MR['seq_step[73]']['addr'])
      L.AND(L.local_MR['seq_step[36]']['name'], L.local_MR['seq_step[36]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[72]']['name'], L.local_MR['seq_step_reset1[72]']['addr'])

      #;Process:moveP@77
      L.LD(L.local_MR['seq_step[1073]']['name'], L.local_MR['seq_step[1073]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[74]']['name'], L.local_MR['seq_step_reset1[74]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1074]']['name'], L.local_MR['seq_step[1074]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[74]']['name'], L.local_MR['seq_step[74]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[74]']['name'], L.local_T['move_static_timer[74]']['addr'])
      L.ANPB(L.local_MR['seq_step[74]']['name'], L.local_MR['seq_step[74]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1074]']['name'], L.local_MR['seq_step[1074]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1074]']['name'], L.local_MR['seq_step[1074]']['addr'])
      #;Post-Process:moveP@77
      #;timeout:moveP@77
      L.LD(L.local_MR['seq_step[74]']['name'], L.local_MR['seq_step[74]']['addr'])
      L.TMS(L.local_T['block_timeout[74]']['addr'], 60000000)
      L.LDP(L.local_T['block_timeout[74]']['name'], L.local_T['block_timeout[74]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+74, message='moveP@77:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+74, error_yaml=error_yaml)
      #;error:moveP@77
      L.LD(L.local_MR['seq_step[74]']['name'], L.local_MR['seq_step[74]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+74, message=f"moveP@77:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+74, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+74, message='moveP@77:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+74, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+74, message='moveP@77:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+74, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@77
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[74]']['name'], L.local_MR['seq_step[74]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[73]']['name'], L.local_MR['seq_step_reset1[73]']['addr'])
      L.LDP(L.local_MR['seq_step[74]']['name'], L.local_MR['seq_step[74]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool, posture = L.FB_setRobotParam(227.146, -10.351, 62.285, 0.0, 0.0, -32.643, 100.0, 100.0, 100.0, 0.1, 0.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, 60, program_override)
        RAC.send_command(f'moveAbsolutePtp({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {json.dumps({'TOOL': 1, 'USER': 1, 'POSTURE': posture, 'VEL': vel, 'ACC': acc, 'DEC': dec})})')
      L.LD(L.local_MR['seq_step[74]']['name'], L.local_MR['seq_step[74]']['addr'])
      L.ANB(L.local_MR['seq_step[1074]']['name'], L.local_MR['seq_step[1074]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {dist})')
      L.LD(L.local_MR['seq_step[74]']['name'], L.local_MR['seq_step[74]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[74]']['addr'], 0.0)
      L.LD(L.local_MR['seq_step[74]']['name'], L.local_MR['seq_step[74]']['addr'])
      L.OUT(L.local_MR['robot_busy[74]']['name'], L.local_MR['robot_busy[74]']['addr'])

      #;Process:set_speed@78
      L.LD(L.local_MR['seq_step[1074]']['name'], L.local_MR['seq_step[1074]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[75]']['name'], L.local_MR['seq_step_reset1[75]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1075]']['name'], L.local_MR['seq_step[1075]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[75]']['name'], L.local_MR['seq_step[75]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.ANPB(L.local_MR['seq_step[75]']['name'], L.local_MR['seq_step[75]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1075]']['name'], L.local_MR['seq_step[1075]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1075]']['name'], L.local_MR['seq_step[1075]']['addr'])
      #;Post-Process:set_speed@78
      #;action:set_speed@78
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[75]']['name'], L.local_MR['seq_step[75]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[74]']['name'], L.local_MR['seq_step_reset1[74]']['addr'])
      L.LDP(L.local_MR['seq_step[75]']['name'], L.local_MR['seq_step[75]']['addr'])
      if (L.aax & L.iix):
        program_override = 100

      #;Process:moveP@79
      L.LD(L.local_MR['seq_step[1075]']['name'], L.local_MR['seq_step[1075]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[76]']['name'], L.local_MR['seq_step_reset1[76]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1076]']['name'], L.local_MR['seq_step[1076]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[76]']['name'], L.local_MR['seq_step[76]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[76]']['name'], L.local_T['move_static_timer[76]']['addr'])
      L.ANPB(L.local_MR['seq_step[76]']['name'], L.local_MR['seq_step[76]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1076]']['name'], L.local_MR['seq_step[1076]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1076]']['name'], L.local_MR['seq_step[1076]']['addr'])
      #;Post-Process:moveP@79
      #;timeout:moveP@79
      L.LD(L.local_MR['seq_step[76]']['name'], L.local_MR['seq_step[76]']['addr'])
      L.TMS(L.local_T['block_timeout[76]']['addr'], 60000000)
      L.LDP(L.local_T['block_timeout[76]']['name'], L.local_T['block_timeout[76]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+76, message='moveP@79:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+76, error_yaml=error_yaml)
      #;error:moveP@79
      L.LD(L.local_MR['seq_step[76]']['name'], L.local_MR['seq_step[76]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+76, message=f"moveP@79:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+76, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+76, message='moveP@79:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+76, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+76, message='moveP@79:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+76, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@79
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[76]']['name'], L.local_MR['seq_step[76]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[75]']['name'], L.local_MR['seq_step_reset1[75]']['addr'])
      L.LDP(L.local_MR['seq_step[76]']['name'], L.local_MR['seq_step[76]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool, posture = L.FB_setRobotParam(227.146, -10.351, 62.285, 0.0, 0.0, -32.643, 100.0, 100.0, 100.0, 0.1, 0.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, 60, program_override)
        RAC.send_command(f'moveAbsolutePtp({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {json.dumps({'TOOL': 1, 'USER': 1, 'POSTURE': posture, 'VEL': vel, 'ACC': acc, 'DEC': dec})})')
      L.LD(L.local_MR['seq_step[76]']['name'], L.local_MR['seq_step[76]']['addr'])
      L.ANB(L.local_MR['seq_step[1076]']['name'], L.local_MR['seq_step[1076]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {dist})')
      L.LD(L.local_MR['seq_step[76]']['name'], L.local_MR['seq_step[76]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[76]']['addr'], 0.0)
      L.LD(L.local_MR['seq_step[76]']['name'], L.local_MR['seq_step[76]']['addr'])
      L.OUT(L.local_MR['robot_busy[76]']['name'], L.local_MR['robot_busy[76]']['addr'])

      #;Process:return@80
      L.LD(L.local_MR['seq_step[1076]']['name'], L.local_MR['seq_step[1076]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[77]']['name'], L.local_MR['seq_step_reset1[77]']['addr'])
      L.MPS()
      L.ANB(L.local_MR['seq_step[1077]']['name'], L.local_MR['seq_step[1077]']['addr'])
      L.OUT(L.local_MR['seq_step[77]']['name'], L.local_MR['seq_step[77]']['addr'])
      L.MPP()
      L.LDPB(L.local_MR['seq_step[77]']['name'], L.local_MR['seq_step[77]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1077]']['name'], L.local_MR['seq_step[1077]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1077]']['name'], L.local_MR['seq_step[1077]']['addr'])
      #;Post-Process:return@80
      #;action:return@80
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[77]']['name'], L.local_MR['seq_step[77]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[76]']['name'], L.local_MR['seq_step_reset1[76]']['addr'])
      L.LDP(L.local_MR['seq_step[77]']['name'], L.local_MR['seq_step[77]']['addr'])
      if (L.aax & L.iix):
        elapsed_time = int((time.perf_counter() - start_time) * 1000)
        L.EM_relay[2020:2020+len(helper.int32_to_uint16s(elapsed_time))] = helper.int32_to_uint16s(elapsed_time)


      #;Process:procedures_defnoreturn@81
      L.LD(L.local_MR['seq_step[11]']['name'], L.local_MR['seq_step[11]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[78]']['name'], L.local_MR['seq_step_reset1[78]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1078]']['name'], L.local_MR['seq_step[1078]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[78]']['name'], L.local_MR['seq_step[78]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.ANPB(L.local_MR['seq_step[78]']['name'], L.local_MR['seq_step[78]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1078]']['name'], L.local_MR['seq_step[1078]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1078]']['name'], L.local_MR['seq_step[1078]']['addr'])
      #;Post-Process:procedures_defnoreturn@81

      #;Process:moveP@82
      L.LD(L.local_MR['seq_step[1078]']['name'], L.local_MR['seq_step[1078]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[79]']['name'], L.local_MR['seq_step_reset1[79]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1079]']['name'], L.local_MR['seq_step[1079]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[79]']['name'], L.local_MR['seq_step[79]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[79]']['name'], L.local_T['move_static_timer[79]']['addr'])
      L.ANPB(L.local_MR['seq_step[79]']['name'], L.local_MR['seq_step[79]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1079]']['name'], L.local_MR['seq_step[1079]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1079]']['name'], L.local_MR['seq_step[1079]']['addr'])
      #;Post-Process:moveP@82
      #;timeout:moveP@82
      L.LD(L.local_MR['seq_step[79]']['name'], L.local_MR['seq_step[79]']['addr'])
      L.TMS(L.local_T['block_timeout[79]']['addr'], 60000000)
      L.LDP(L.local_T['block_timeout[79]']['name'], L.local_T['block_timeout[79]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+79, message='moveP@82:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+79, error_yaml=error_yaml)
      #;error:moveP@82
      L.LD(L.local_MR['seq_step[79]']['name'], L.local_MR['seq_step[79]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+79, message=f"moveP@82:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+79, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+79, message='moveP@82:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+79, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+79, message='moveP@82:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+79, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@82
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[79]']['name'], L.local_MR['seq_step[79]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[78]']['name'], L.local_MR['seq_step_reset1[78]']['addr'])
      L.LDP(L.local_MR['seq_step[79]']['name'], L.local_MR['seq_step[79]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool, posture = L.FB_setRobotParam(227.146, -10.351, 62.285, 0.0, 0.0, -32.643, 100.0, 100.0, 100.0, 0.1, 0.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, 60, program_override)
        RAC.send_command(f'moveAbsolutePtp({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {json.dumps({'TOOL': 1, 'USER': 1, 'POSTURE': posture, 'VEL': vel, 'ACC': acc, 'DEC': dec})})')
      L.LD(L.local_MR['seq_step[79]']['name'], L.local_MR['seq_step[79]']['addr'])
      L.ANB(L.local_MR['seq_step[1079]']['name'], L.local_MR['seq_step[1079]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {dist})')
      L.LD(L.local_MR['seq_step[79]']['name'], L.local_MR['seq_step[79]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[79]']['addr'], 0.0)
      L.LD(L.local_MR['seq_step[79]']['name'], L.local_MR['seq_step[79]']['addr'])
      L.OUT(L.local_MR['robot_busy[79]']['name'], L.local_MR['robot_busy[79]']['addr'])

      #;Process:moveP@83
      L.LD(L.local_MR['seq_step[1079]']['name'], L.local_MR['seq_step[1079]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[80]']['name'], L.local_MR['seq_step_reset1[80]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1080]']['name'], L.local_MR['seq_step[1080]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[80]']['name'], L.local_MR['seq_step[80]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[80]']['name'], L.local_T['move_static_timer[80]']['addr'])
      L.ANPB(L.local_MR['seq_step[80]']['name'], L.local_MR['seq_step[80]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1080]']['name'], L.local_MR['seq_step[1080]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1080]']['name'], L.local_MR['seq_step[1080]']['addr'])
      #;Post-Process:moveP@83
      #;timeout:moveP@83
      L.LD(L.local_MR['seq_step[80]']['name'], L.local_MR['seq_step[80]']['addr'])
      L.TMS(L.local_T['block_timeout[80]']['addr'], 60000000)
      L.LDP(L.local_T['block_timeout[80]']['name'], L.local_T['block_timeout[80]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+80, message='moveP@83:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+80, error_yaml=error_yaml)
      #;error:moveP@83
      L.LD(L.local_MR['seq_step[80]']['name'], L.local_MR['seq_step[80]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+80, message=f"moveP@83:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+80, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+80, message='moveP@83:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+80, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+80, message='moveP@83:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+80, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@83
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[80]']['name'], L.local_MR['seq_step[80]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[79]']['name'], L.local_MR['seq_step_reset1[79]']['addr'])
      L.LDP(L.local_MR['seq_step[80]']['name'], L.local_MR['seq_step[80]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool, posture = L.FB_setRobotParam(227.146, -10.351, 62.285, 0.0, 0.0, -32.643, 100.0, 100.0, 100.0, 0.1, 0.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, 60, program_override)
        RAC.send_command(f'moveAbsolutePtp({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {json.dumps({'TOOL': 1, 'USER': 1, 'POSTURE': posture, 'VEL': vel, 'ACC': acc, 'DEC': dec})})')
      L.LD(L.local_MR['seq_step[80]']['name'], L.local_MR['seq_step[80]']['addr'])
      L.ANB(L.local_MR['seq_step[1080]']['name'], L.local_MR['seq_step[1080]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {dist})')
      L.LD(L.local_MR['seq_step[80]']['name'], L.local_MR['seq_step[80]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[80]']['addr'], 0.0)
      L.LD(L.local_MR['seq_step[80]']['name'], L.local_MR['seq_step[80]']['addr'])
      L.OUT(L.local_MR['robot_busy[80]']['name'], L.local_MR['robot_busy[80]']['addr'])

      #;Process:set_speed@84
      L.LD(L.local_MR['seq_step[1080]']['name'], L.local_MR['seq_step[1080]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[81]']['name'], L.local_MR['seq_step_reset1[81]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1081]']['name'], L.local_MR['seq_step[1081]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[81]']['name'], L.local_MR['seq_step[81]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.ANPB(L.local_MR['seq_step[81]']['name'], L.local_MR['seq_step[81]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1081]']['name'], L.local_MR['seq_step[1081]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1081]']['name'], L.local_MR['seq_step[1081]']['addr'])
      #;Post-Process:set_speed@84
      #;action:set_speed@84
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[81]']['name'], L.local_MR['seq_step[81]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[80]']['name'], L.local_MR['seq_step_reset1[80]']['addr'])
      L.LDP(L.local_MR['seq_step[81]']['name'], L.local_MR['seq_step[81]']['addr'])
      if (L.aax & L.iix):
        program_override = 100

      #;Process:moveP@85
      L.LD(L.local_MR['seq_step[1081]']['name'], L.local_MR['seq_step[1081]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[82]']['name'], L.local_MR['seq_step_reset1[82]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1082]']['name'], L.local_MR['seq_step[1082]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[82]']['name'], L.local_MR['seq_step[82]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[82]']['name'], L.local_T['move_static_timer[82]']['addr'])
      L.ANPB(L.local_MR['seq_step[82]']['name'], L.local_MR['seq_step[82]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1082]']['name'], L.local_MR['seq_step[1082]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1082]']['name'], L.local_MR['seq_step[1082]']['addr'])
      #;Post-Process:moveP@85
      #;timeout:moveP@85
      L.LD(L.local_MR['seq_step[82]']['name'], L.local_MR['seq_step[82]']['addr'])
      L.TMS(L.local_T['block_timeout[82]']['addr'], 60000000)
      L.LDP(L.local_T['block_timeout[82]']['name'], L.local_T['block_timeout[82]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+82, message='moveP@85:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+82, error_yaml=error_yaml)
      #;error:moveP@85
      L.LD(L.local_MR['seq_step[82]']['name'], L.local_MR['seq_step[82]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+82, message=f"moveP@85:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+82, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+82, message='moveP@85:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+82, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+82, message='moveP@85:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+82, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@85
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[82]']['name'], L.local_MR['seq_step[82]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[81]']['name'], L.local_MR['seq_step_reset1[81]']['addr'])
      L.LDP(L.local_MR['seq_step[82]']['name'], L.local_MR['seq_step[82]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool, posture = L.FB_setRobotParam(227.146, -10.351, 62.285, 0.0, 0.0, -32.643, 100.0, 100.0, 100.0, 0.1, 0.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, 60, program_override)
        RAC.send_command(f'moveAbsolutePtp({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {json.dumps({'TOOL': 1, 'USER': 1, 'POSTURE': posture, 'VEL': vel, 'ACC': acc, 'DEC': dec})})')
      L.LD(L.local_MR['seq_step[82]']['name'], L.local_MR['seq_step[82]']['addr'])
      L.ANB(L.local_MR['seq_step[1082]']['name'], L.local_MR['seq_step[1082]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {dist})')
      L.LD(L.local_MR['seq_step[82]']['name'], L.local_MR['seq_step[82]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[82]']['addr'], 0.0)
      L.LD(L.local_MR['seq_step[82]']['name'], L.local_MR['seq_step[82]']['addr'])
      L.OUT(L.local_MR['robot_busy[82]']['name'], L.local_MR['robot_busy[82]']['addr'])

      #;Process:procedures_callnoreturn@86
      L.LD(L.local_MR['seq_step[1082]']['name'], L.local_MR['seq_step[1082]']['addr'])
      L.MPS()
      L.LDB(L.local_MR['seq_step[1083]']['name'], L.local_MR['seq_step[1083]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[83]']['name'], L.local_MR['seq_step[83]']['addr'])
      L.MPP()
      L.LD(L.local_MR['seq_step[1030]']['name'], L.local_MR['seq_step[1030]']['addr'])
      L.ANPB(L.local_MR['seq_step[83]']['name'], L.local_MR['seq_step[83]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1083]']['name'], L.local_MR['seq_step[1083]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1083]']['name'], L.local_MR['seq_step[1083]']['addr'])
      #;Post-Process:procedures_callnoreturn@86
      #;action:procedures_callnoreturn@86
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[83]']['name'], L.local_MR['seq_step[83]']['addr'])
      L.AND(L.local_MR['seq_step[26]']['name'], L.local_MR['seq_step[26]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[82]']['name'], L.local_MR['seq_step_reset1[82]']['addr'])

      #;Process:wait_timer@87
      L.LD(L.local_MR['seq_step[1083]']['name'], L.local_MR['seq_step[1083]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[84]']['name'], L.local_MR['seq_step_reset1[84]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1084]']['name'], L.local_MR['seq_step[1084]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[84]']['name'], L.local_MR['seq_step[84]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(L.local_T['block_timer1[84]']['name'], L.local_T['block_timer1[84]']['addr'])
      L.ANPB(L.local_MR['seq_step[84]']['name'], L.local_MR['seq_step[84]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1084]']['name'], L.local_MR['seq_step[1084]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1084]']['name'], L.local_MR['seq_step[1084]']['addr'])
      #;Post-Process:wait_timer@87
      #;timeout:wait_timer@87
      L.LD(L.local_MR['seq_step[84]']['name'], L.local_MR['seq_step[84]']['addr'])
      L.TMS(L.local_T['block_timeout[84]']['addr'], 60000)
      L.LDP(L.local_T['block_timeout[84]']['name'], L.local_T['block_timeout[84]']['addr'])
      if (L.aax & L.iix):
        drive.register_error(no=801+84, message='wait_timer@87:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+84, error_yaml=error_yaml)
      #;action:wait_timer@87
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[84]']['name'], L.local_MR['seq_step[84]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[83]']['name'], L.local_MR['seq_step_reset1[83]']['addr'])
      L.LD(L.local_MR['seq_step[84]']['name'], L.local_MR['seq_step[84]']['addr'])
      L.TMS(L.local_T['block_timer1[84]']['addr'], wait_msec=number_param_yaml['N1']['value'])

      #;Process:moveP@88
      L.LD(L.local_MR['seq_step[1084]']['name'], L.local_MR['seq_step[1084]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[85]']['name'], L.local_MR['seq_step_reset1[85]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1085]']['name'], L.local_MR['seq_step[1085]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[85]']['name'], L.local_MR['seq_step[85]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[85]']['name'], L.local_T['move_static_timer[85]']['addr'])
      L.ANPB(L.local_MR['seq_step[85]']['name'], L.local_MR['seq_step[85]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1085]']['name'], L.local_MR['seq_step[1085]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1085]']['name'], L.local_MR['seq_step[1085]']['addr'])
      #;Post-Process:moveP@88
      #;timeout:moveP@88
      L.LD(L.local_MR['seq_step[85]']['name'], L.local_MR['seq_step[85]']['addr'])
      L.TMS(L.local_T['block_timeout[85]']['addr'], 60000000)
      L.LDP(L.local_T['block_timeout[85]']['name'], L.local_T['block_timeout[85]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+85, message='moveP@88:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+85, error_yaml=error_yaml)
      #;error:moveP@88
      L.LD(L.local_MR['seq_step[85]']['name'], L.local_MR['seq_step[85]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+85, message=f"moveP@88:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+85, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+85, message='moveP@88:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+85, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+85, message='moveP@88:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+85, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@88
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[85]']['name'], L.local_MR['seq_step[85]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[84]']['name'], L.local_MR['seq_step_reset1[84]']['addr'])
      L.LDP(L.local_MR['seq_step[85]']['name'], L.local_MR['seq_step[85]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool, posture = L.FB_setRobotParam(227.146, -10.351, 62.285, 0.0, 0.0, -32.643, 100.0, 100.0, 100.0, 0.1, 0.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, 60, program_override)
        RAC.send_command(f'moveAbsolutePtp({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {json.dumps({'TOOL': 1, 'USER': 1, 'POSTURE': posture, 'VEL': vel, 'ACC': acc, 'DEC': dec})})')
      L.LD(L.local_MR['seq_step[85]']['name'], L.local_MR['seq_step[85]']['addr'])
      L.ANB(L.local_MR['seq_step[1085]']['name'], L.local_MR['seq_step[1085]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {dist})')
      L.LD(L.local_MR['seq_step[85]']['name'], L.local_MR['seq_step[85]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[85]']['addr'], 0.0)
      L.LD(L.local_MR['seq_step[85]']['name'], L.local_MR['seq_step[85]']['addr'])
      L.OUT(L.local_MR['robot_busy[85]']['name'], L.local_MR['robot_busy[85]']['addr'])

      #;Process:set_speed@89
      L.LD(L.local_MR['seq_step[1085]']['name'], L.local_MR['seq_step[1085]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[86]']['name'], L.local_MR['seq_step_reset1[86]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1086]']['name'], L.local_MR['seq_step[1086]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[86]']['name'], L.local_MR['seq_step[86]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.ANPB(L.local_MR['seq_step[86]']['name'], L.local_MR['seq_step[86]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1086]']['name'], L.local_MR['seq_step[1086]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1086]']['name'], L.local_MR['seq_step[1086]']['addr'])
      #;Post-Process:set_speed@89
      #;action:set_speed@89
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[86]']['name'], L.local_MR['seq_step[86]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[85]']['name'], L.local_MR['seq_step_reset1[85]']['addr'])
      L.LDP(L.local_MR['seq_step[86]']['name'], L.local_MR['seq_step[86]']['addr'])
      if (L.aax & L.iix):
        program_override = 100

      #;Process:moveP@90
      L.LD(L.local_MR['seq_step[1086]']['name'], L.local_MR['seq_step[1086]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[87]']['name'], L.local_MR['seq_step_reset1[87]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1087]']['name'], L.local_MR['seq_step[1087]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[87]']['name'], L.local_MR['seq_step[87]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[87]']['name'], L.local_T['move_static_timer[87]']['addr'])
      L.ANPB(L.local_MR['seq_step[87]']['name'], L.local_MR['seq_step[87]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1087]']['name'], L.local_MR['seq_step[1087]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1087]']['name'], L.local_MR['seq_step[1087]']['addr'])
      #;Post-Process:moveP@90
      #;timeout:moveP@90
      L.LD(L.local_MR['seq_step[87]']['name'], L.local_MR['seq_step[87]']['addr'])
      L.TMS(L.local_T['block_timeout[87]']['addr'], 60000000)
      L.LDP(L.local_T['block_timeout[87]']['name'], L.local_T['block_timeout[87]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+87, message='moveP@90:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+87, error_yaml=error_yaml)
      #;error:moveP@90
      L.LD(L.local_MR['seq_step[87]']['name'], L.local_MR['seq_step[87]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+87, message=f"moveP@90:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+87, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+87, message='moveP@90:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+87, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+87, message='moveP@90:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+87, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@90
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[87]']['name'], L.local_MR['seq_step[87]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[86]']['name'], L.local_MR['seq_step_reset1[86]']['addr'])
      L.LDP(L.local_MR['seq_step[87]']['name'], L.local_MR['seq_step[87]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool, posture = L.FB_setRobotParam(227.146, -10.351, 62.285, 0.0, 0.0, -32.643, 100.0, 100.0, 100.0, 0.1, 0.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, 60, program_override)
        RAC.send_command(f'moveAbsolutePtp({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {json.dumps({'TOOL': 1, 'USER': 1, 'POSTURE': posture, 'VEL': vel, 'ACC': acc, 'DEC': dec})})')
      L.LD(L.local_MR['seq_step[87]']['name'], L.local_MR['seq_step[87]']['addr'])
      L.ANB(L.local_MR['seq_step[1087]']['name'], L.local_MR['seq_step[1087]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {dist})')
      L.LD(L.local_MR['seq_step[87]']['name'], L.local_MR['seq_step[87]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[87]']['addr'], 0.0)
      L.LD(L.local_MR['seq_step[87]']['name'], L.local_MR['seq_step[87]']['addr'])
      L.OUT(L.local_MR['robot_busy[87]']['name'], L.local_MR['robot_busy[87]']['addr'])

      #;Process:return@91
      L.LD(L.local_MR['seq_step[1087]']['name'], L.local_MR['seq_step[1087]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[88]']['name'], L.local_MR['seq_step_reset1[88]']['addr'])
      L.MPS()
      L.ANB(L.local_MR['seq_step[1088]']['name'], L.local_MR['seq_step[1088]']['addr'])
      L.OUT(L.local_MR['seq_step[88]']['name'], L.local_MR['seq_step[88]']['addr'])
      L.MPP()
      L.LDPB(L.local_MR['seq_step[88]']['name'], L.local_MR['seq_step[88]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1088]']['name'], L.local_MR['seq_step[1088]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1088]']['name'], L.local_MR['seq_step[1088]']['addr'])
      #;Post-Process:return@91
      #;action:return@91
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[88]']['name'], L.local_MR['seq_step[88]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[87]']['name'], L.local_MR['seq_step_reset1[87]']['addr'])
      L.LDP(L.local_MR['seq_step[88]']['name'], L.local_MR['seq_step[88]']['addr'])
      if (L.aax & L.iix):
        elapsed_time = int((time.perf_counter() - start_time) * 1000)
        L.EM_relay[2020:2020+len(helper.int32_to_uint16s(elapsed_time))] = helper.int32_to_uint16s(elapsed_time)


      #;Process:procedures_defnoreturn@92
      L.LD(L.local_MR['seq_step[15]']['name'], L.local_MR['seq_step[15]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[89]']['name'], L.local_MR['seq_step_reset1[89]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1089]']['name'], L.local_MR['seq_step[1089]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[89]']['name'], L.local_MR['seq_step[89]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.ANPB(L.local_MR['seq_step[89]']['name'], L.local_MR['seq_step[89]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1089]']['name'], L.local_MR['seq_step[1089]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1089]']['name'], L.local_MR['seq_step[1089]']['addr'])
      #;Post-Process:procedures_defnoreturn@92

      #;Process:moveP@93
      L.LD(L.local_MR['seq_step[1089]']['name'], L.local_MR['seq_step[1089]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[90]']['name'], L.local_MR['seq_step_reset1[90]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1090]']['name'], L.local_MR['seq_step[1090]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[90]']['name'], L.local_MR['seq_step[90]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[90]']['name'], L.local_T['move_static_timer[90]']['addr'])
      L.ANPB(L.local_MR['seq_step[90]']['name'], L.local_MR['seq_step[90]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1090]']['name'], L.local_MR['seq_step[1090]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1090]']['name'], L.local_MR['seq_step[1090]']['addr'])
      #;Post-Process:moveP@93
      #;timeout:moveP@93
      L.LD(L.local_MR['seq_step[90]']['name'], L.local_MR['seq_step[90]']['addr'])
      L.TMS(L.local_T['block_timeout[90]']['addr'], 60000000)
      L.LDP(L.local_T['block_timeout[90]']['name'], L.local_T['block_timeout[90]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+90, message='moveP@93:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+90, error_yaml=error_yaml)
      #;error:moveP@93
      L.LD(L.local_MR['seq_step[90]']['name'], L.local_MR['seq_step[90]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+90, message=f"moveP@93:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+90, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+90, message='moveP@93:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+90, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+90, message='moveP@93:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+90, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@93
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[90]']['name'], L.local_MR['seq_step[90]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[89]']['name'], L.local_MR['seq_step_reset1[89]']['addr'])
      L.LDP(L.local_MR['seq_step[90]']['name'], L.local_MR['seq_step[90]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool, posture = L.FB_setRobotParam(227.146, -10.351, 62.285, 0.0, 0.0, -32.643, 100.0, 100.0, 100.0, 0.1, 0.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, 60, program_override)
        RAC.send_command(f'moveAbsolutePtp({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {json.dumps({'TOOL': 1, 'USER': 1, 'POSTURE': posture, 'VEL': vel, 'ACC': acc, 'DEC': dec})})')
      L.LD(L.local_MR['seq_step[90]']['name'], L.local_MR['seq_step[90]']['addr'])
      L.ANB(L.local_MR['seq_step[1090]']['name'], L.local_MR['seq_step[1090]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {dist})')
      L.LD(L.local_MR['seq_step[90]']['name'], L.local_MR['seq_step[90]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[90]']['addr'], 0.0)
      L.LD(L.local_MR['seq_step[90]']['name'], L.local_MR['seq_step[90]']['addr'])
      L.OUT(L.local_MR['robot_busy[90]']['name'], L.local_MR['robot_busy[90]']['addr'])

      #;Process:moveP@94
      L.LD(L.local_MR['seq_step[1090]']['name'], L.local_MR['seq_step[1090]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[91]']['name'], L.local_MR['seq_step_reset1[91]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1091]']['name'], L.local_MR['seq_step[1091]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[91]']['name'], L.local_MR['seq_step[91]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[91]']['name'], L.local_T['move_static_timer[91]']['addr'])
      L.ANPB(L.local_MR['seq_step[91]']['name'], L.local_MR['seq_step[91]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1091]']['name'], L.local_MR['seq_step[1091]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1091]']['name'], L.local_MR['seq_step[1091]']['addr'])
      #;Post-Process:moveP@94
      #;timeout:moveP@94
      L.LD(L.local_MR['seq_step[91]']['name'], L.local_MR['seq_step[91]']['addr'])
      L.TMS(L.local_T['block_timeout[91]']['addr'], 60000000)
      L.LDP(L.local_T['block_timeout[91]']['name'], L.local_T['block_timeout[91]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+91, message='moveP@94:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+91, error_yaml=error_yaml)
      #;error:moveP@94
      L.LD(L.local_MR['seq_step[91]']['name'], L.local_MR['seq_step[91]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+91, message=f"moveP@94:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+91, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+91, message='moveP@94:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+91, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+91, message='moveP@94:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+91, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@94
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[91]']['name'], L.local_MR['seq_step[91]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[90]']['name'], L.local_MR['seq_step_reset1[90]']['addr'])
      L.LDP(L.local_MR['seq_step[91]']['name'], L.local_MR['seq_step[91]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool, posture = L.FB_setRobotParam(227.146, -10.351, 62.285, 0.0, 0.0, -32.643, 100.0, 100.0, 100.0, 0.1, 0.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, 60, program_override)
        RAC.send_command(f'moveAbsolutePtp({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {json.dumps({'TOOL': 1, 'USER': 1, 'POSTURE': posture, 'VEL': vel, 'ACC': acc, 'DEC': dec})})')
      L.LD(L.local_MR['seq_step[91]']['name'], L.local_MR['seq_step[91]']['addr'])
      L.ANB(L.local_MR['seq_step[1091]']['name'], L.local_MR['seq_step[1091]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {dist})')
      L.LD(L.local_MR['seq_step[91]']['name'], L.local_MR['seq_step[91]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[91]']['addr'], 0.0)
      L.LD(L.local_MR['seq_step[91]']['name'], L.local_MR['seq_step[91]']['addr'])
      L.OUT(L.local_MR['robot_busy[91]']['name'], L.local_MR['robot_busy[91]']['addr'])

      #;Process:procedures_callnoreturn@95
      L.LD(L.local_MR['seq_step[1091]']['name'], L.local_MR['seq_step[1091]']['addr'])
      L.MPS()
      L.LDB(L.local_MR['seq_step[1092]']['name'], L.local_MR['seq_step[1092]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[92]']['name'], L.local_MR['seq_step[92]']['addr'])
      L.MPP()
      L.LD(L.local_MR['seq_step[1040]']['name'], L.local_MR['seq_step[1040]']['addr'])
      L.ANPB(L.local_MR['seq_step[92]']['name'], L.local_MR['seq_step[92]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1092]']['name'], L.local_MR['seq_step[1092]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1092]']['name'], L.local_MR['seq_step[1092]']['addr'])
      #;Post-Process:procedures_callnoreturn@95
      #;action:procedures_callnoreturn@95
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[92]']['name'], L.local_MR['seq_step[92]']['addr'])
      L.AND(L.local_MR['seq_step[36]']['name'], L.local_MR['seq_step[36]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[91]']['name'], L.local_MR['seq_step_reset1[91]']['addr'])

      #;Process:set_speed@96
      L.LD(L.local_MR['seq_step[1092]']['name'], L.local_MR['seq_step[1092]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[93]']['name'], L.local_MR['seq_step_reset1[93]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1093]']['name'], L.local_MR['seq_step[1093]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[93]']['name'], L.local_MR['seq_step[93]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.ANPB(L.local_MR['seq_step[93]']['name'], L.local_MR['seq_step[93]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1093]']['name'], L.local_MR['seq_step[1093]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1093]']['name'], L.local_MR['seq_step[1093]']['addr'])
      #;Post-Process:set_speed@96
      #;action:set_speed@96
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[93]']['name'], L.local_MR['seq_step[93]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[92]']['name'], L.local_MR['seq_step_reset1[92]']['addr'])
      L.LDP(L.local_MR['seq_step[93]']['name'], L.local_MR['seq_step[93]']['addr'])
      if (L.aax & L.iix):
        program_override = 100

      #;Process:moveP@97
      L.LD(L.local_MR['seq_step[1093]']['name'], L.local_MR['seq_step[1093]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[94]']['name'], L.local_MR['seq_step_reset1[94]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1094]']['name'], L.local_MR['seq_step[1094]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[94]']['name'], L.local_MR['seq_step[94]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[94]']['name'], L.local_T['move_static_timer[94]']['addr'])
      L.ANPB(L.local_MR['seq_step[94]']['name'], L.local_MR['seq_step[94]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1094]']['name'], L.local_MR['seq_step[1094]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1094]']['name'], L.local_MR['seq_step[1094]']['addr'])
      #;Post-Process:moveP@97
      #;timeout:moveP@97
      L.LD(L.local_MR['seq_step[94]']['name'], L.local_MR['seq_step[94]']['addr'])
      L.TMS(L.local_T['block_timeout[94]']['addr'], 60000000)
      L.LDP(L.local_T['block_timeout[94]']['name'], L.local_T['block_timeout[94]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+94, message='moveP@97:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+94, error_yaml=error_yaml)
      #;error:moveP@97
      L.LD(L.local_MR['seq_step[94]']['name'], L.local_MR['seq_step[94]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+94, message=f"moveP@97:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+94, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+94, message='moveP@97:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+94, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+94, message='moveP@97:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+94, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@97
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[94]']['name'], L.local_MR['seq_step[94]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[93]']['name'], L.local_MR['seq_step_reset1[93]']['addr'])
      L.LDP(L.local_MR['seq_step[94]']['name'], L.local_MR['seq_step[94]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool, posture = L.FB_setRobotParam(227.146, -10.351, 62.285, 0.0, 0.0, -32.643, 100.0, 100.0, 100.0, 0.1, 0.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, 60, program_override)
        RAC.send_command(f'moveAbsolutePtp({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {json.dumps({'TOOL': 1, 'USER': 1, 'POSTURE': posture, 'VEL': vel, 'ACC': acc, 'DEC': dec})})')
      L.LD(L.local_MR['seq_step[94]']['name'], L.local_MR['seq_step[94]']['addr'])
      L.ANB(L.local_MR['seq_step[1094]']['name'], L.local_MR['seq_step[1094]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {dist})')
      L.LD(L.local_MR['seq_step[94]']['name'], L.local_MR['seq_step[94]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[94]']['addr'], 0.0)
      L.LD(L.local_MR['seq_step[94]']['name'], L.local_MR['seq_step[94]']['addr'])
      L.OUT(L.local_MR['robot_busy[94]']['name'], L.local_MR['robot_busy[94]']['addr'])

      #;Process:procedures_callnoreturn@98
      L.LD(L.local_MR['seq_step[1094]']['name'], L.local_MR['seq_step[1094]']['addr'])
      L.MPS()
      L.LDB(L.local_MR['seq_step[1095]']['name'], L.local_MR['seq_step[1095]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[95]']['name'], L.local_MR['seq_step[95]']['addr'])
      L.MPP()
      L.LD(L.local_MR['seq_step[1045]']['name'], L.local_MR['seq_step[1045]']['addr'])
      L.ANPB(L.local_MR['seq_step[95]']['name'], L.local_MR['seq_step[95]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1095]']['name'], L.local_MR['seq_step[1095]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1095]']['name'], L.local_MR['seq_step[1095]']['addr'])
      #;Post-Process:procedures_callnoreturn@98
      #;action:procedures_callnoreturn@98
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[95]']['name'], L.local_MR['seq_step[95]']['addr'])
      L.AND(L.local_MR['seq_step[41]']['name'], L.local_MR['seq_step[41]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[94]']['name'], L.local_MR['seq_step_reset1[94]']['addr'])

      #;Process:set_speed@99
      L.LD(L.local_MR['seq_step[1095]']['name'], L.local_MR['seq_step[1095]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[96]']['name'], L.local_MR['seq_step_reset1[96]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1096]']['name'], L.local_MR['seq_step[1096]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[96]']['name'], L.local_MR['seq_step[96]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.ANPB(L.local_MR['seq_step[96]']['name'], L.local_MR['seq_step[96]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1096]']['name'], L.local_MR['seq_step[1096]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1096]']['name'], L.local_MR['seq_step[1096]']['addr'])
      #;Post-Process:set_speed@99
      #;action:set_speed@99
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[96]']['name'], L.local_MR['seq_step[96]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[95]']['name'], L.local_MR['seq_step_reset1[95]']['addr'])
      L.LDP(L.local_MR['seq_step[96]']['name'], L.local_MR['seq_step[96]']['addr'])
      if (L.aax & L.iix):
        program_override = 100

      #;Process:moveP@100
      L.LD(L.local_MR['seq_step[1096]']['name'], L.local_MR['seq_step[1096]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[97]']['name'], L.local_MR['seq_step_reset1[97]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1097]']['name'], L.local_MR['seq_step[1097]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[97]']['name'], L.local_MR['seq_step[97]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[97]']['name'], L.local_T['move_static_timer[97]']['addr'])
      L.ANPB(L.local_MR['seq_step[97]']['name'], L.local_MR['seq_step[97]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1097]']['name'], L.local_MR['seq_step[1097]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1097]']['name'], L.local_MR['seq_step[1097]']['addr'])
      #;Post-Process:moveP@100
      #;timeout:moveP@100
      L.LD(L.local_MR['seq_step[97]']['name'], L.local_MR['seq_step[97]']['addr'])
      L.TMS(L.local_T['block_timeout[97]']['addr'], 60000000)
      L.LDP(L.local_T['block_timeout[97]']['name'], L.local_T['block_timeout[97]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+97, message='moveP@100:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+97, error_yaml=error_yaml)
      #;error:moveP@100
      L.LD(L.local_MR['seq_step[97]']['name'], L.local_MR['seq_step[97]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+97, message=f"moveP@100:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+97, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+97, message='moveP@100:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+97, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+97, message='moveP@100:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+97, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@100
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[97]']['name'], L.local_MR['seq_step[97]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[96]']['name'], L.local_MR['seq_step_reset1[96]']['addr'])
      L.LDP(L.local_MR['seq_step[97]']['name'], L.local_MR['seq_step[97]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool, posture = L.FB_setRobotParam(227.146, -10.351, 62.285, 0.0, 0.0, -32.643, 100.0, 100.0, 100.0, 0.1, 0.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, 60, program_override)
        RAC.send_command(f'moveAbsolutePtp({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {json.dumps({'TOOL': 1, 'USER': 1, 'POSTURE': posture, 'VEL': vel, 'ACC': acc, 'DEC': dec})})')
      L.LD(L.local_MR['seq_step[97]']['name'], L.local_MR['seq_step[97]']['addr'])
      L.ANB(L.local_MR['seq_step[1097]']['name'], L.local_MR['seq_step[1097]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {dist})')
      L.LD(L.local_MR['seq_step[97]']['name'], L.local_MR['seq_step[97]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[97]']['addr'], 0.0)
      L.LD(L.local_MR['seq_step[97]']['name'], L.local_MR['seq_step[97]']['addr'])
      L.OUT(L.local_MR['robot_busy[97]']['name'], L.local_MR['robot_busy[97]']['addr'])

      #;Process:moveP@101
      L.LD(L.local_MR['seq_step[1097]']['name'], L.local_MR['seq_step[1097]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[98]']['name'], L.local_MR['seq_step_reset1[98]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1098]']['name'], L.local_MR['seq_step[1098]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[98]']['name'], L.local_MR['seq_step[98]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[98]']['name'], L.local_T['move_static_timer[98]']['addr'])
      L.ANPB(L.local_MR['seq_step[98]']['name'], L.local_MR['seq_step[98]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1098]']['name'], L.local_MR['seq_step[1098]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1098]']['name'], L.local_MR['seq_step[1098]']['addr'])
      #;Post-Process:moveP@101
      #;timeout:moveP@101
      L.LD(L.local_MR['seq_step[98]']['name'], L.local_MR['seq_step[98]']['addr'])
      L.TMS(L.local_T['block_timeout[98]']['addr'], 60000000)
      L.LDP(L.local_T['block_timeout[98]']['name'], L.local_T['block_timeout[98]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+98, message='moveP@101:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+98, error_yaml=error_yaml)
      #;error:moveP@101
      L.LD(L.local_MR['seq_step[98]']['name'], L.local_MR['seq_step[98]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+98, message=f"moveP@101:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+98, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+98, message='moveP@101:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+98, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+98, message='moveP@101:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+98, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@101
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[98]']['name'], L.local_MR['seq_step[98]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[97]']['name'], L.local_MR['seq_step_reset1[97]']['addr'])
      L.LDP(L.local_MR['seq_step[98]']['name'], L.local_MR['seq_step[98]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool, posture = L.FB_setRobotParam(227.146, -10.351, 62.285, 0.0, 0.0, -32.643, 100.0, 100.0, 100.0, 0.1, 0.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, 60, program_override)
        RAC.send_command(f'moveAbsolutePtp({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {json.dumps({'TOOL': 1, 'USER': 1, 'POSTURE': posture, 'VEL': vel, 'ACC': acc, 'DEC': dec})})')
      L.LD(L.local_MR['seq_step[98]']['name'], L.local_MR['seq_step[98]']['addr'])
      L.ANB(L.local_MR['seq_step[1098]']['name'], L.local_MR['seq_step[1098]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {dist})')
      L.LD(L.local_MR['seq_step[98]']['name'], L.local_MR['seq_step[98]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[98]']['addr'], 0.0)
      L.LD(L.local_MR['seq_step[98]']['name'], L.local_MR['seq_step[98]']['addr'])
      L.OUT(L.local_MR['robot_busy[98]']['name'], L.local_MR['robot_busy[98]']['addr'])

      #;Process:return@102
      L.LD(L.local_MR['seq_step[1098]']['name'], L.local_MR['seq_step[1098]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[99]']['name'], L.local_MR['seq_step_reset1[99]']['addr'])
      L.MPS()
      L.ANB(L.local_MR['seq_step[1099]']['name'], L.local_MR['seq_step[1099]']['addr'])
      L.OUT(L.local_MR['seq_step[99]']['name'], L.local_MR['seq_step[99]']['addr'])
      L.MPP()
      L.LDPB(L.local_MR['seq_step[99]']['name'], L.local_MR['seq_step[99]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1099]']['name'], L.local_MR['seq_step[1099]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1099]']['name'], L.local_MR['seq_step[1099]']['addr'])
      #;Post-Process:return@102
      #;action:return@102
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[99]']['name'], L.local_MR['seq_step[99]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[98]']['name'], L.local_MR['seq_step_reset1[98]']['addr'])
      L.LDP(L.local_MR['seq_step[99]']['name'], L.local_MR['seq_step[99]']['addr'])
      if (L.aax & L.iix):
        elapsed_time = int((time.perf_counter() - start_time) * 1000)
        L.EM_relay[2020:2020+len(helper.int32_to_uint16s(elapsed_time))] = helper.int32_to_uint16s(elapsed_time)


      #;Process:procedures_defnoreturn@103
      L.LD(L.local_MR['seq_step[17]']['name'], L.local_MR['seq_step[17]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[100]']['name'], L.local_MR['seq_step_reset1[100]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1100]']['name'], L.local_MR['seq_step[1100]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[100]']['name'], L.local_MR['seq_step[100]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.ANPB(L.local_MR['seq_step[100]']['name'], L.local_MR['seq_step[100]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1100]']['name'], L.local_MR['seq_step[1100]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1100]']['name'], L.local_MR['seq_step[1100]']['addr'])
      #;Post-Process:procedures_defnoreturn@103

      #;Process:moveP@104
      L.LD(L.local_MR['seq_step[1100]']['name'], L.local_MR['seq_step[1100]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[101]']['name'], L.local_MR['seq_step_reset1[101]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1101]']['name'], L.local_MR['seq_step[1101]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[101]']['name'], L.local_MR['seq_step[101]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[101]']['name'], L.local_T['move_static_timer[101]']['addr'])
      L.ANPB(L.local_MR['seq_step[101]']['name'], L.local_MR['seq_step[101]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1101]']['name'], L.local_MR['seq_step[1101]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1101]']['name'], L.local_MR['seq_step[1101]']['addr'])
      #;Post-Process:moveP@104
      #;timeout:moveP@104
      L.LD(L.local_MR['seq_step[101]']['name'], L.local_MR['seq_step[101]']['addr'])
      L.TMS(L.local_T['block_timeout[101]']['addr'], 60000000)
      L.LDP(L.local_T['block_timeout[101]']['name'], L.local_T['block_timeout[101]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+101, message='moveP@104:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+101, error_yaml=error_yaml)
      #;error:moveP@104
      L.LD(L.local_MR['seq_step[101]']['name'], L.local_MR['seq_step[101]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+101, message=f"moveP@104:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+101, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+101, message='moveP@104:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+101, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+101, message='moveP@104:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+101, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@104
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[101]']['name'], L.local_MR['seq_step[101]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[100]']['name'], L.local_MR['seq_step_reset1[100]']['addr'])
      L.LDP(L.local_MR['seq_step[101]']['name'], L.local_MR['seq_step[101]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool, posture = L.FB_setRobotParam(227.146, -10.351, 62.285, 0.0, 0.0, -32.643, 100.0, 100.0, 100.0, 0.1, 0.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, 60, program_override)
        RAC.send_command(f'moveAbsolutePtp({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {json.dumps({'TOOL': 1, 'USER': 1, 'POSTURE': posture, 'VEL': vel, 'ACC': acc, 'DEC': dec})})')
      L.LD(L.local_MR['seq_step[101]']['name'], L.local_MR['seq_step[101]']['addr'])
      L.ANB(L.local_MR['seq_step[1101]']['name'], L.local_MR['seq_step[1101]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {dist})')
      L.LD(L.local_MR['seq_step[101]']['name'], L.local_MR['seq_step[101]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[101]']['addr'], 0.0)
      L.LD(L.local_MR['seq_step[101]']['name'], L.local_MR['seq_step[101]']['addr'])
      L.OUT(L.local_MR['robot_busy[101]']['name'], L.local_MR['robot_busy[101]']['addr'])

      #;Process:moveP@105
      L.LD(L.local_MR['seq_step[1101]']['name'], L.local_MR['seq_step[1101]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[102]']['name'], L.local_MR['seq_step_reset1[102]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1102]']['name'], L.local_MR['seq_step[1102]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[102]']['name'], L.local_MR['seq_step[102]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[102]']['name'], L.local_T['move_static_timer[102]']['addr'])
      L.ANPB(L.local_MR['seq_step[102]']['name'], L.local_MR['seq_step[102]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1102]']['name'], L.local_MR['seq_step[1102]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1102]']['name'], L.local_MR['seq_step[1102]']['addr'])
      #;Post-Process:moveP@105
      #;timeout:moveP@105
      L.LD(L.local_MR['seq_step[102]']['name'], L.local_MR['seq_step[102]']['addr'])
      L.TMS(L.local_T['block_timeout[102]']['addr'], 60000000)
      L.LDP(L.local_T['block_timeout[102]']['name'], L.local_T['block_timeout[102]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+102, message='moveP@105:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+102, error_yaml=error_yaml)
      #;error:moveP@105
      L.LD(L.local_MR['seq_step[102]']['name'], L.local_MR['seq_step[102]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+102, message=f"moveP@105:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+102, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+102, message='moveP@105:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+102, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+102, message='moveP@105:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+102, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@105
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[102]']['name'], L.local_MR['seq_step[102]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[101]']['name'], L.local_MR['seq_step_reset1[101]']['addr'])
      L.LDP(L.local_MR['seq_step[102]']['name'], L.local_MR['seq_step[102]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool, posture = L.FB_setRobotParam(227.146, -10.351, 62.285, 0.0, 0.0, -32.643, 100.0, 100.0, 100.0, 0.1, 0.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, 60, program_override)
        RAC.send_command(f'moveAbsolutePtp({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {json.dumps({'TOOL': 1, 'USER': 1, 'POSTURE': posture, 'VEL': vel, 'ACC': acc, 'DEC': dec})})')
      L.LD(L.local_MR['seq_step[102]']['name'], L.local_MR['seq_step[102]']['addr'])
      L.ANB(L.local_MR['seq_step[1102]']['name'], L.local_MR['seq_step[1102]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {dist})')
      L.LD(L.local_MR['seq_step[102]']['name'], L.local_MR['seq_step[102]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[102]']['addr'], 0.0)
      L.LD(L.local_MR['seq_step[102]']['name'], L.local_MR['seq_step[102]']['addr'])
      L.OUT(L.local_MR['robot_busy[102]']['name'], L.local_MR['robot_busy[102]']['addr'])

      #;Process:set_speed@106
      L.LD(L.local_MR['seq_step[1102]']['name'], L.local_MR['seq_step[1102]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[103]']['name'], L.local_MR['seq_step_reset1[103]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1103]']['name'], L.local_MR['seq_step[1103]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[103]']['name'], L.local_MR['seq_step[103]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.ANPB(L.local_MR['seq_step[103]']['name'], L.local_MR['seq_step[103]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1103]']['name'], L.local_MR['seq_step[1103]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1103]']['name'], L.local_MR['seq_step[1103]']['addr'])
      #;Post-Process:set_speed@106
      #;action:set_speed@106
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[103]']['name'], L.local_MR['seq_step[103]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[102]']['name'], L.local_MR['seq_step_reset1[102]']['addr'])
      L.LDP(L.local_MR['seq_step[103]']['name'], L.local_MR['seq_step[103]']['addr'])
      if (L.aax & L.iix):
        program_override = 100

      #;Process:moveP@107
      L.LD(L.local_MR['seq_step[1103]']['name'], L.local_MR['seq_step[1103]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[104]']['name'], L.local_MR['seq_step_reset1[104]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1104]']['name'], L.local_MR['seq_step[1104]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[104]']['name'], L.local_MR['seq_step[104]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[104]']['name'], L.local_T['move_static_timer[104]']['addr'])
      L.ANPB(L.local_MR['seq_step[104]']['name'], L.local_MR['seq_step[104]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1104]']['name'], L.local_MR['seq_step[1104]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1104]']['name'], L.local_MR['seq_step[1104]']['addr'])
      #;Post-Process:moveP@107
      #;timeout:moveP@107
      L.LD(L.local_MR['seq_step[104]']['name'], L.local_MR['seq_step[104]']['addr'])
      L.TMS(L.local_T['block_timeout[104]']['addr'], 60000000)
      L.LDP(L.local_T['block_timeout[104]']['name'], L.local_T['block_timeout[104]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+104, message='moveP@107:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+104, error_yaml=error_yaml)
      #;error:moveP@107
      L.LD(L.local_MR['seq_step[104]']['name'], L.local_MR['seq_step[104]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+104, message=f"moveP@107:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+104, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+104, message='moveP@107:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+104, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+104, message='moveP@107:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+104, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@107
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[104]']['name'], L.local_MR['seq_step[104]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[103]']['name'], L.local_MR['seq_step_reset1[103]']['addr'])
      L.LDP(L.local_MR['seq_step[104]']['name'], L.local_MR['seq_step[104]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool, posture = L.FB_setRobotParam(227.146, -10.351, 62.285, 0.0, 0.0, -32.643, 100.0, 100.0, 100.0, 0.1, 0.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, 60, program_override)
        RAC.send_command(f'moveAbsolutePtp({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {json.dumps({'TOOL': 1, 'USER': 1, 'POSTURE': posture, 'VEL': vel, 'ACC': acc, 'DEC': dec})})')
      L.LD(L.local_MR['seq_step[104]']['name'], L.local_MR['seq_step[104]']['addr'])
      L.ANB(L.local_MR['seq_step[1104]']['name'], L.local_MR['seq_step[1104]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {dist})')
      L.LD(L.local_MR['seq_step[104]']['name'], L.local_MR['seq_step[104]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[104]']['addr'], 0.0)
      L.LD(L.local_MR['seq_step[104]']['name'], L.local_MR['seq_step[104]']['addr'])
      L.OUT(L.local_MR['robot_busy[104]']['name'], L.local_MR['robot_busy[104]']['addr'])

      #;Process:procedures_callnoreturn@108
      L.LD(L.local_MR['seq_step[1104]']['name'], L.local_MR['seq_step[1104]']['addr'])
      L.MPS()
      L.LDB(L.local_MR['seq_step[1105]']['name'], L.local_MR['seq_step[1105]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[105]']['name'], L.local_MR['seq_step[105]']['addr'])
      L.MPP()
      L.LD(L.local_MR['seq_step[1040]']['name'], L.local_MR['seq_step[1040]']['addr'])
      L.ANPB(L.local_MR['seq_step[105]']['name'], L.local_MR['seq_step[105]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1105]']['name'], L.local_MR['seq_step[1105]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1105]']['name'], L.local_MR['seq_step[1105]']['addr'])
      #;Post-Process:procedures_callnoreturn@108
      #;action:procedures_callnoreturn@108
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[105]']['name'], L.local_MR['seq_step[105]']['addr'])
      L.AND(L.local_MR['seq_step[36]']['name'], L.local_MR['seq_step[36]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[104]']['name'], L.local_MR['seq_step_reset1[104]']['addr'])

      #;Process:moveP@109
      L.LD(L.local_MR['seq_step[1105]']['name'], L.local_MR['seq_step[1105]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[106]']['name'], L.local_MR['seq_step_reset1[106]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1106]']['name'], L.local_MR['seq_step[1106]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[106]']['name'], L.local_MR['seq_step[106]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[106]']['name'], L.local_T['move_static_timer[106]']['addr'])
      L.ANPB(L.local_MR['seq_step[106]']['name'], L.local_MR['seq_step[106]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1106]']['name'], L.local_MR['seq_step[1106]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1106]']['name'], L.local_MR['seq_step[1106]']['addr'])
      #;Post-Process:moveP@109
      #;timeout:moveP@109
      L.LD(L.local_MR['seq_step[106]']['name'], L.local_MR['seq_step[106]']['addr'])
      L.TMS(L.local_T['block_timeout[106]']['addr'], 60000000)
      L.LDP(L.local_T['block_timeout[106]']['name'], L.local_T['block_timeout[106]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+106, message='moveP@109:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+106, error_yaml=error_yaml)
      #;error:moveP@109
      L.LD(L.local_MR['seq_step[106]']['name'], L.local_MR['seq_step[106]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+106, message=f"moveP@109:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+106, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+106, message='moveP@109:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+106, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+106, message='moveP@109:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+106, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@109
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[106]']['name'], L.local_MR['seq_step[106]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[105]']['name'], L.local_MR['seq_step_reset1[105]']['addr'])
      L.LDP(L.local_MR['seq_step[106]']['name'], L.local_MR['seq_step[106]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool, posture = L.FB_setRobotParam(227.146, -10.351, 62.285, 0.0, 0.0, -32.643, 100.0, 100.0, 100.0, 0.1, 0.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, 60, program_override)
        RAC.send_command(f'moveAbsolutePtp({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {json.dumps({'TOOL': 1, 'USER': 1, 'POSTURE': posture, 'VEL': vel, 'ACC': acc, 'DEC': dec})})')
      L.LD(L.local_MR['seq_step[106]']['name'], L.local_MR['seq_step[106]']['addr'])
      L.ANB(L.local_MR['seq_step[1106]']['name'], L.local_MR['seq_step[1106]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {dist})')
      L.LD(L.local_MR['seq_step[106]']['name'], L.local_MR['seq_step[106]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[106]']['addr'], 0.0)
      L.LD(L.local_MR['seq_step[106]']['name'], L.local_MR['seq_step[106]']['addr'])
      L.OUT(L.local_MR['robot_busy[106]']['name'], L.local_MR['robot_busy[106]']['addr'])

      #;Process:set_speed@110
      L.LD(L.local_MR['seq_step[1106]']['name'], L.local_MR['seq_step[1106]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[107]']['name'], L.local_MR['seq_step_reset1[107]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1107]']['name'], L.local_MR['seq_step[1107]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[107]']['name'], L.local_MR['seq_step[107]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.ANPB(L.local_MR['seq_step[107]']['name'], L.local_MR['seq_step[107]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1107]']['name'], L.local_MR['seq_step[1107]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1107]']['name'], L.local_MR['seq_step[1107]']['addr'])
      #;Post-Process:set_speed@110
      #;action:set_speed@110
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[107]']['name'], L.local_MR['seq_step[107]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[106]']['name'], L.local_MR['seq_step_reset1[106]']['addr'])
      L.LDP(L.local_MR['seq_step[107]']['name'], L.local_MR['seq_step[107]']['addr'])
      if (L.aax & L.iix):
        program_override = 100

      #;Process:moveP@111
      L.LD(L.local_MR['seq_step[1107]']['name'], L.local_MR['seq_step[1107]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[108]']['name'], L.local_MR['seq_step_reset1[108]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1108]']['name'], L.local_MR['seq_step[1108]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[108]']['name'], L.local_MR['seq_step[108]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[108]']['name'], L.local_T['move_static_timer[108]']['addr'])
      L.ANPB(L.local_MR['seq_step[108]']['name'], L.local_MR['seq_step[108]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1108]']['name'], L.local_MR['seq_step[1108]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1108]']['name'], L.local_MR['seq_step[1108]']['addr'])
      #;Post-Process:moveP@111
      #;timeout:moveP@111
      L.LD(L.local_MR['seq_step[108]']['name'], L.local_MR['seq_step[108]']['addr'])
      L.TMS(L.local_T['block_timeout[108]']['addr'], 60000000)
      L.LDP(L.local_T['block_timeout[108]']['name'], L.local_T['block_timeout[108]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+108, message='moveP@111:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+108, error_yaml=error_yaml)
      #;error:moveP@111
      L.LD(L.local_MR['seq_step[108]']['name'], L.local_MR['seq_step[108]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+108, message=f"moveP@111:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+108, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+108, message='moveP@111:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+108, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+108, message='moveP@111:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+108, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@111
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[108]']['name'], L.local_MR['seq_step[108]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[107]']['name'], L.local_MR['seq_step_reset1[107]']['addr'])
      L.LDP(L.local_MR['seq_step[108]']['name'], L.local_MR['seq_step[108]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool, posture = L.FB_setRobotParam(227.146, -10.351, 62.285, 0.0, 0.0, -32.643, 100.0, 100.0, 100.0, 0.1, 0.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, 60, program_override)
        RAC.send_command(f'moveAbsolutePtp({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {json.dumps({'TOOL': 1, 'USER': 1, 'POSTURE': posture, 'VEL': vel, 'ACC': acc, 'DEC': dec})})')
      L.LD(L.local_MR['seq_step[108]']['name'], L.local_MR['seq_step[108]']['addr'])
      L.ANB(L.local_MR['seq_step[1108]']['name'], L.local_MR['seq_step[1108]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {dist})')
      L.LD(L.local_MR['seq_step[108]']['name'], L.local_MR['seq_step[108]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[108]']['addr'], 0.0)
      L.LD(L.local_MR['seq_step[108]']['name'], L.local_MR['seq_step[108]']['addr'])
      L.OUT(L.local_MR['robot_busy[108]']['name'], L.local_MR['robot_busy[108]']['addr'])

      #;Process:return@112
      L.LD(L.local_MR['seq_step[1108]']['name'], L.local_MR['seq_step[1108]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[109]']['name'], L.local_MR['seq_step_reset1[109]']['addr'])
      L.MPS()
      L.ANB(L.local_MR['seq_step[1109]']['name'], L.local_MR['seq_step[1109]']['addr'])
      L.OUT(L.local_MR['seq_step[109]']['name'], L.local_MR['seq_step[109]']['addr'])
      L.MPP()
      L.LDPB(L.local_MR['seq_step[109]']['name'], L.local_MR['seq_step[109]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1109]']['name'], L.local_MR['seq_step[1109]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1109]']['name'], L.local_MR['seq_step[1109]']['addr'])
      #;Post-Process:return@112
      #;action:return@112
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[109]']['name'], L.local_MR['seq_step[109]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[108]']['name'], L.local_MR['seq_step_reset1[108]']['addr'])
      L.LDP(L.local_MR['seq_step[109]']['name'], L.local_MR['seq_step[109]']['addr'])
      if (L.aax & L.iix):
        elapsed_time = int((time.perf_counter() - start_time) * 1000)
        L.EM_relay[2020:2020+len(helper.int32_to_uint16s(elapsed_time))] = helper.int32_to_uint16s(elapsed_time)


      #;Process:procedures_defnoreturn@113
      L.LD(L.local_MR['seq_step[19]']['name'], L.local_MR['seq_step[19]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[110]']['name'], L.local_MR['seq_step_reset1[110]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1110]']['name'], L.local_MR['seq_step[1110]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[110]']['name'], L.local_MR['seq_step[110]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.ANPB(L.local_MR['seq_step[110]']['name'], L.local_MR['seq_step[110]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1110]']['name'], L.local_MR['seq_step[1110]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1110]']['name'], L.local_MR['seq_step[1110]']['addr'])
      #;Post-Process:procedures_defnoreturn@113

      #;Process:moveP@114
      L.LD(L.local_MR['seq_step[1110]']['name'], L.local_MR['seq_step[1110]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[111]']['name'], L.local_MR['seq_step_reset1[111]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1111]']['name'], L.local_MR['seq_step[1111]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[111]']['name'], L.local_MR['seq_step[111]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[111]']['name'], L.local_T['move_static_timer[111]']['addr'])
      L.ANPB(L.local_MR['seq_step[111]']['name'], L.local_MR['seq_step[111]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1111]']['name'], L.local_MR['seq_step[1111]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1111]']['name'], L.local_MR['seq_step[1111]']['addr'])
      #;Post-Process:moveP@114
      #;timeout:moveP@114
      L.LD(L.local_MR['seq_step[111]']['name'], L.local_MR['seq_step[111]']['addr'])
      L.TMS(L.local_T['block_timeout[111]']['addr'], 60000000)
      L.LDP(L.local_T['block_timeout[111]']['name'], L.local_T['block_timeout[111]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+111, message='moveP@114:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+111, error_yaml=error_yaml)
      #;error:moveP@114
      L.LD(L.local_MR['seq_step[111]']['name'], L.local_MR['seq_step[111]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+111, message=f"moveP@114:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+111, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+111, message='moveP@114:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+111, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+111, message='moveP@114:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+111, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@114
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[111]']['name'], L.local_MR['seq_step[111]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[110]']['name'], L.local_MR['seq_step_reset1[110]']['addr'])
      L.LDP(L.local_MR['seq_step[111]']['name'], L.local_MR['seq_step[111]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool, posture = L.FB_setRobotParam(227.146, -10.351, 62.285, 0.0, 0.0, -32.643, 100.0, 100.0, 100.0, 0.1, 0.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, 60, program_override)
        RAC.send_command(f'moveAbsolutePtp({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {json.dumps({'TOOL': 1, 'USER': 1, 'POSTURE': posture, 'VEL': vel, 'ACC': acc, 'DEC': dec})})')
      L.LD(L.local_MR['seq_step[111]']['name'], L.local_MR['seq_step[111]']['addr'])
      L.ANB(L.local_MR['seq_step[1111]']['name'], L.local_MR['seq_step[1111]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {dist})')
      L.LD(L.local_MR['seq_step[111]']['name'], L.local_MR['seq_step[111]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[111]']['addr'], 0.0)
      L.LD(L.local_MR['seq_step[111]']['name'], L.local_MR['seq_step[111]']['addr'])
      L.OUT(L.local_MR['robot_busy[111]']['name'], L.local_MR['robot_busy[111]']['addr'])

      #;Process:moveP@115
      L.LD(L.local_MR['seq_step[1111]']['name'], L.local_MR['seq_step[1111]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[112]']['name'], L.local_MR['seq_step_reset1[112]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1112]']['name'], L.local_MR['seq_step[1112]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[112]']['name'], L.local_MR['seq_step[112]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[112]']['name'], L.local_T['move_static_timer[112]']['addr'])
      L.ANPB(L.local_MR['seq_step[112]']['name'], L.local_MR['seq_step[112]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1112]']['name'], L.local_MR['seq_step[1112]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1112]']['name'], L.local_MR['seq_step[1112]']['addr'])
      #;Post-Process:moveP@115
      #;timeout:moveP@115
      L.LD(L.local_MR['seq_step[112]']['name'], L.local_MR['seq_step[112]']['addr'])
      L.TMS(L.local_T['block_timeout[112]']['addr'], 60000000)
      L.LDP(L.local_T['block_timeout[112]']['name'], L.local_T['block_timeout[112]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+112, message='moveP@115:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+112, error_yaml=error_yaml)
      #;error:moveP@115
      L.LD(L.local_MR['seq_step[112]']['name'], L.local_MR['seq_step[112]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+112, message=f"moveP@115:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+112, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+112, message='moveP@115:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+112, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+112, message='moveP@115:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+112, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@115
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[112]']['name'], L.local_MR['seq_step[112]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[111]']['name'], L.local_MR['seq_step_reset1[111]']['addr'])
      L.LDP(L.local_MR['seq_step[112]']['name'], L.local_MR['seq_step[112]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool, posture = L.FB_setRobotParam(227.146, -10.351, 62.285, 0.0, 0.0, -32.643, 100.0, 100.0, 100.0, 0.1, 0.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, 60, program_override)
        RAC.send_command(f'moveAbsolutePtp({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {json.dumps({'TOOL': 1, 'USER': 1, 'POSTURE': posture, 'VEL': vel, 'ACC': acc, 'DEC': dec})})')
      L.LD(L.local_MR['seq_step[112]']['name'], L.local_MR['seq_step[112]']['addr'])
      L.ANB(L.local_MR['seq_step[1112]']['name'], L.local_MR['seq_step[1112]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {dist})')
      L.LD(L.local_MR['seq_step[112]']['name'], L.local_MR['seq_step[112]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[112]']['addr'], 0.0)
      L.LD(L.local_MR['seq_step[112]']['name'], L.local_MR['seq_step[112]']['addr'])
      L.OUT(L.local_MR['robot_busy[112]']['name'], L.local_MR['robot_busy[112]']['addr'])

      #;Process:procedures_callnoreturn@116
      L.LD(L.local_MR['seq_step[1112]']['name'], L.local_MR['seq_step[1112]']['addr'])
      L.MPS()
      L.LDB(L.local_MR['seq_step[1113]']['name'], L.local_MR['seq_step[1113]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[113]']['name'], L.local_MR['seq_step[113]']['addr'])
      L.MPP()
      L.LD(L.local_MR['seq_step[1030]']['name'], L.local_MR['seq_step[1030]']['addr'])
      L.ANPB(L.local_MR['seq_step[113]']['name'], L.local_MR['seq_step[113]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1113]']['name'], L.local_MR['seq_step[1113]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1113]']['name'], L.local_MR['seq_step[1113]']['addr'])
      #;Post-Process:procedures_callnoreturn@116
      #;action:procedures_callnoreturn@116
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[113]']['name'], L.local_MR['seq_step[113]']['addr'])
      L.AND(L.local_MR['seq_step[26]']['name'], L.local_MR['seq_step[26]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[112]']['name'], L.local_MR['seq_step_reset1[112]']['addr'])

      #;Process:set_speed@117
      L.LD(L.local_MR['seq_step[1113]']['name'], L.local_MR['seq_step[1113]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[114]']['name'], L.local_MR['seq_step_reset1[114]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1114]']['name'], L.local_MR['seq_step[1114]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[114]']['name'], L.local_MR['seq_step[114]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.ANPB(L.local_MR['seq_step[114]']['name'], L.local_MR['seq_step[114]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1114]']['name'], L.local_MR['seq_step[1114]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1114]']['name'], L.local_MR['seq_step[1114]']['addr'])
      #;Post-Process:set_speed@117
      #;action:set_speed@117
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[114]']['name'], L.local_MR['seq_step[114]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[113]']['name'], L.local_MR['seq_step_reset1[113]']['addr'])
      L.LDP(L.local_MR['seq_step[114]']['name'], L.local_MR['seq_step[114]']['addr'])
      if (L.aax & L.iix):
        program_override = 100

      #;Process:moveP@118
      L.LD(L.local_MR['seq_step[1114]']['name'], L.local_MR['seq_step[1114]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[115]']['name'], L.local_MR['seq_step_reset1[115]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1115]']['name'], L.local_MR['seq_step[1115]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[115]']['name'], L.local_MR['seq_step[115]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[115]']['name'], L.local_T['move_static_timer[115]']['addr'])
      L.ANPB(L.local_MR['seq_step[115]']['name'], L.local_MR['seq_step[115]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1115]']['name'], L.local_MR['seq_step[1115]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1115]']['name'], L.local_MR['seq_step[1115]']['addr'])
      #;Post-Process:moveP@118
      #;timeout:moveP@118
      L.LD(L.local_MR['seq_step[115]']['name'], L.local_MR['seq_step[115]']['addr'])
      L.TMS(L.local_T['block_timeout[115]']['addr'], 60000000)
      L.LDP(L.local_T['block_timeout[115]']['name'], L.local_T['block_timeout[115]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+115, message='moveP@118:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+115, error_yaml=error_yaml)
      #;error:moveP@118
      L.LD(L.local_MR['seq_step[115]']['name'], L.local_MR['seq_step[115]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+115, message=f"moveP@118:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+115, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+115, message='moveP@118:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+115, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+115, message='moveP@118:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+115, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@118
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[115]']['name'], L.local_MR['seq_step[115]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[114]']['name'], L.local_MR['seq_step_reset1[114]']['addr'])
      L.LDP(L.local_MR['seq_step[115]']['name'], L.local_MR['seq_step[115]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool, posture = L.FB_setRobotParam(227.146, -10.351, 62.285, 0.0, 0.0, -32.643, 100.0, 100.0, 100.0, 0.1, 0.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, 60, program_override)
        RAC.send_command(f'moveAbsolutePtp({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {json.dumps({'TOOL': 1, 'USER': 1, 'POSTURE': posture, 'VEL': vel, 'ACC': acc, 'DEC': dec})})')
      L.LD(L.local_MR['seq_step[115]']['name'], L.local_MR['seq_step[115]']['addr'])
      L.ANB(L.local_MR['seq_step[1115]']['name'], L.local_MR['seq_step[1115]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {dist})')
      L.LD(L.local_MR['seq_step[115]']['name'], L.local_MR['seq_step[115]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[115]']['addr'], 0.0)
      L.LD(L.local_MR['seq_step[115]']['name'], L.local_MR['seq_step[115]']['addr'])
      L.OUT(L.local_MR['robot_busy[115]']['name'], L.local_MR['robot_busy[115]']['addr'])

      #;Process:procedures_callnoreturn@119
      L.LD(L.local_MR['seq_step[1115]']['name'], L.local_MR['seq_step[1115]']['addr'])
      L.MPS()
      L.LDB(L.local_MR['seq_step[1116]']['name'], L.local_MR['seq_step[1116]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[116]']['name'], L.local_MR['seq_step[116]']['addr'])
      L.MPP()
      L.LD(L.local_MR['seq_step[1035]']['name'], L.local_MR['seq_step[1035]']['addr'])
      L.ANPB(L.local_MR['seq_step[116]']['name'], L.local_MR['seq_step[116]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1116]']['name'], L.local_MR['seq_step[1116]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1116]']['name'], L.local_MR['seq_step[1116]']['addr'])
      #;Post-Process:procedures_callnoreturn@119
      #;action:procedures_callnoreturn@119
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[116]']['name'], L.local_MR['seq_step[116]']['addr'])
      L.AND(L.local_MR['seq_step[31]']['name'], L.local_MR['seq_step[31]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[115]']['name'], L.local_MR['seq_step_reset1[115]']['addr'])

      #;Process:set_speed@120
      L.LD(L.local_MR['seq_step[1116]']['name'], L.local_MR['seq_step[1116]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[117]']['name'], L.local_MR['seq_step_reset1[117]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1117]']['name'], L.local_MR['seq_step[1117]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[117]']['name'], L.local_MR['seq_step[117]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.ANPB(L.local_MR['seq_step[117]']['name'], L.local_MR['seq_step[117]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1117]']['name'], L.local_MR['seq_step[1117]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1117]']['name'], L.local_MR['seq_step[1117]']['addr'])
      #;Post-Process:set_speed@120
      #;action:set_speed@120
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[117]']['name'], L.local_MR['seq_step[117]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[116]']['name'], L.local_MR['seq_step_reset1[116]']['addr'])
      L.LDP(L.local_MR['seq_step[117]']['name'], L.local_MR['seq_step[117]']['addr'])
      if (L.aax & L.iix):
        program_override = 100

      #;Process:moveP@121
      L.LD(L.local_MR['seq_step[1117]']['name'], L.local_MR['seq_step[1117]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[118]']['name'], L.local_MR['seq_step_reset1[118]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1118]']['name'], L.local_MR['seq_step[1118]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[118]']['name'], L.local_MR['seq_step[118]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[118]']['name'], L.local_T['move_static_timer[118]']['addr'])
      L.ANPB(L.local_MR['seq_step[118]']['name'], L.local_MR['seq_step[118]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1118]']['name'], L.local_MR['seq_step[1118]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1118]']['name'], L.local_MR['seq_step[1118]']['addr'])
      #;Post-Process:moveP@121
      #;timeout:moveP@121
      L.LD(L.local_MR['seq_step[118]']['name'], L.local_MR['seq_step[118]']['addr'])
      L.TMS(L.local_T['block_timeout[118]']['addr'], 60000000)
      L.LDP(L.local_T['block_timeout[118]']['name'], L.local_T['block_timeout[118]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+118, message='moveP@121:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+118, error_yaml=error_yaml)
      #;error:moveP@121
      L.LD(L.local_MR['seq_step[118]']['name'], L.local_MR['seq_step[118]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+118, message=f"moveP@121:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+118, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+118, message='moveP@121:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+118, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+118, message='moveP@121:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+118, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@121
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[118]']['name'], L.local_MR['seq_step[118]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[117]']['name'], L.local_MR['seq_step_reset1[117]']['addr'])
      L.LDP(L.local_MR['seq_step[118]']['name'], L.local_MR['seq_step[118]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool, posture = L.FB_setRobotParam(227.146, -10.351, 62.285, 0.0, 0.0, -32.643, 100.0, 100.0, 100.0, 0.1, 0.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, 60, program_override)
        RAC.send_command(f'moveAbsolutePtp({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {json.dumps({'TOOL': 1, 'USER': 1, 'POSTURE': posture, 'VEL': vel, 'ACC': acc, 'DEC': dec})})')
      L.LD(L.local_MR['seq_step[118]']['name'], L.local_MR['seq_step[118]']['addr'])
      L.ANB(L.local_MR['seq_step[1118]']['name'], L.local_MR['seq_step[1118]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {dist})')
      L.LD(L.local_MR['seq_step[118]']['name'], L.local_MR['seq_step[118]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[118]']['addr'], 0.0)
      L.LD(L.local_MR['seq_step[118]']['name'], L.local_MR['seq_step[118]']['addr'])
      L.OUT(L.local_MR['robot_busy[118]']['name'], L.local_MR['robot_busy[118]']['addr'])

      #;Process:moveP@122
      L.LD(L.local_MR['seq_step[1118]']['name'], L.local_MR['seq_step[1118]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[119]']['name'], L.local_MR['seq_step_reset1[119]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1119]']['name'], L.local_MR['seq_step[1119]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[119]']['name'], L.local_MR['seq_step[119]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[119]']['name'], L.local_T['move_static_timer[119]']['addr'])
      L.ANPB(L.local_MR['seq_step[119]']['name'], L.local_MR['seq_step[119]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1119]']['name'], L.local_MR['seq_step[1119]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1119]']['name'], L.local_MR['seq_step[1119]']['addr'])
      #;Post-Process:moveP@122
      #;timeout:moveP@122
      L.LD(L.local_MR['seq_step[119]']['name'], L.local_MR['seq_step[119]']['addr'])
      L.TMS(L.local_T['block_timeout[119]']['addr'], 60000000)
      L.LDP(L.local_T['block_timeout[119]']['name'], L.local_T['block_timeout[119]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+119, message='moveP@122:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+119, error_yaml=error_yaml)
      #;error:moveP@122
      L.LD(L.local_MR['seq_step[119]']['name'], L.local_MR['seq_step[119]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+119, message=f"moveP@122:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+119, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+119, message='moveP@122:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+119, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+119, message='moveP@122:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+119, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@122
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[119]']['name'], L.local_MR['seq_step[119]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[118]']['name'], L.local_MR['seq_step_reset1[118]']['addr'])
      L.LDP(L.local_MR['seq_step[119]']['name'], L.local_MR['seq_step[119]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool, posture = L.FB_setRobotParam(227.146, -10.351, 62.285, 0.0, 0.0, -32.643, 100.0, 100.0, 100.0, 0.1, 0.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, 60, program_override)
        RAC.send_command(f'moveAbsolutePtp({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {json.dumps({'TOOL': 1, 'USER': 1, 'POSTURE': posture, 'VEL': vel, 'ACC': acc, 'DEC': dec})})')
      L.LD(L.local_MR['seq_step[119]']['name'], L.local_MR['seq_step[119]']['addr'])
      L.ANB(L.local_MR['seq_step[1119]']['name'], L.local_MR['seq_step[1119]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {dist})')
      L.LD(L.local_MR['seq_step[119]']['name'], L.local_MR['seq_step[119]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[119]']['addr'], 0.0)
      L.LD(L.local_MR['seq_step[119]']['name'], L.local_MR['seq_step[119]']['addr'])
      L.OUT(L.local_MR['robot_busy[119]']['name'], L.local_MR['robot_busy[119]']['addr'])

      #;Process:return@123
      L.LD(L.local_MR['seq_step[1119]']['name'], L.local_MR['seq_step[1119]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[120]']['name'], L.local_MR['seq_step_reset1[120]']['addr'])
      L.MPS()
      L.ANB(L.local_MR['seq_step[1120]']['name'], L.local_MR['seq_step[1120]']['addr'])
      L.OUT(L.local_MR['seq_step[120]']['name'], L.local_MR['seq_step[120]']['addr'])
      L.MPP()
      L.LDPB(L.local_MR['seq_step[120]']['name'], L.local_MR['seq_step[120]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1120]']['name'], L.local_MR['seq_step[1120]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1120]']['name'], L.local_MR['seq_step[1120]']['addr'])
      #;Post-Process:return@123
      #;action:return@123
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[120]']['name'], L.local_MR['seq_step[120]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[119]']['name'], L.local_MR['seq_step_reset1[119]']['addr'])
      L.LDP(L.local_MR['seq_step[120]']['name'], L.local_MR['seq_step[120]']['addr'])
      if (L.aax & L.iix):
        elapsed_time = int((time.perf_counter() - start_time) * 1000)
        L.EM_relay[2020:2020+len(helper.int32_to_uint16s(elapsed_time))] = helper.int32_to_uint16s(elapsed_time)


      #;Process:procedures_defnoreturn@124
      L.LD(L.local_MR['seq_step[20]']['name'], L.local_MR['seq_step[20]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[121]']['name'], L.local_MR['seq_step_reset1[121]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1121]']['name'], L.local_MR['seq_step[1121]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[121]']['name'], L.local_MR['seq_step[121]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.ANPB(L.local_MR['seq_step[121]']['name'], L.local_MR['seq_step[121]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1121]']['name'], L.local_MR['seq_step[1121]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1121]']['name'], L.local_MR['seq_step[1121]']['addr'])
      #;Post-Process:procedures_defnoreturn@124

      #;Process:moveP@125
      L.LD(L.local_MR['seq_step[1121]']['name'], L.local_MR['seq_step[1121]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[122]']['name'], L.local_MR['seq_step_reset1[122]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1122]']['name'], L.local_MR['seq_step[1122]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[122]']['name'], L.local_MR['seq_step[122]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[122]']['name'], L.local_T['move_static_timer[122]']['addr'])
      L.ANPB(L.local_MR['seq_step[122]']['name'], L.local_MR['seq_step[122]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1122]']['name'], L.local_MR['seq_step[1122]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1122]']['name'], L.local_MR['seq_step[1122]']['addr'])
      #;Post-Process:moveP@125
      #;timeout:moveP@125
      L.LD(L.local_MR['seq_step[122]']['name'], L.local_MR['seq_step[122]']['addr'])
      L.TMS(L.local_T['block_timeout[122]']['addr'], 60000000)
      L.LDP(L.local_T['block_timeout[122]']['name'], L.local_T['block_timeout[122]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+122, message='moveP@125:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+122, error_yaml=error_yaml)
      #;error:moveP@125
      L.LD(L.local_MR['seq_step[122]']['name'], L.local_MR['seq_step[122]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+122, message=f"moveP@125:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+122, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+122, message='moveP@125:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+122, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+122, message='moveP@125:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+122, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@125
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[122]']['name'], L.local_MR['seq_step[122]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[121]']['name'], L.local_MR['seq_step_reset1[121]']['addr'])
      L.LDP(L.local_MR['seq_step[122]']['name'], L.local_MR['seq_step[122]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool, posture = L.FB_setRobotParam(227.146, -10.351, 62.285, 0.0, 0.0, -32.643, 100.0, 100.0, 100.0, 0.1, 0.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, 60, program_override)
        RAC.send_command(f'moveAbsolutePtp({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {json.dumps({'TOOL': 1, 'USER': 1, 'POSTURE': posture, 'VEL': vel, 'ACC': acc, 'DEC': dec})})')
      L.LD(L.local_MR['seq_step[122]']['name'], L.local_MR['seq_step[122]']['addr'])
      L.ANB(L.local_MR['seq_step[1122]']['name'], L.local_MR['seq_step[1122]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {dist})')
      L.LD(L.local_MR['seq_step[122]']['name'], L.local_MR['seq_step[122]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[122]']['addr'], 0.0)
      L.LD(L.local_MR['seq_step[122]']['name'], L.local_MR['seq_step[122]']['addr'])
      L.OUT(L.local_MR['robot_busy[122]']['name'], L.local_MR['robot_busy[122]']['addr'])

      #;Process:moveP@126
      L.LD(L.local_MR['seq_step[1122]']['name'], L.local_MR['seq_step[1122]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[123]']['name'], L.local_MR['seq_step_reset1[123]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1123]']['name'], L.local_MR['seq_step[1123]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[123]']['name'], L.local_MR['seq_step[123]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[123]']['name'], L.local_T['move_static_timer[123]']['addr'])
      L.ANPB(L.local_MR['seq_step[123]']['name'], L.local_MR['seq_step[123]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1123]']['name'], L.local_MR['seq_step[1123]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1123]']['name'], L.local_MR['seq_step[1123]']['addr'])
      #;Post-Process:moveP@126
      #;timeout:moveP@126
      L.LD(L.local_MR['seq_step[123]']['name'], L.local_MR['seq_step[123]']['addr'])
      L.TMS(L.local_T['block_timeout[123]']['addr'], 60000000)
      L.LDP(L.local_T['block_timeout[123]']['name'], L.local_T['block_timeout[123]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+123, message='moveP@126:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+123, error_yaml=error_yaml)
      #;error:moveP@126
      L.LD(L.local_MR['seq_step[123]']['name'], L.local_MR['seq_step[123]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+123, message=f"moveP@126:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+123, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+123, message='moveP@126:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+123, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+123, message='moveP@126:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+123, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@126
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[123]']['name'], L.local_MR['seq_step[123]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[122]']['name'], L.local_MR['seq_step_reset1[122]']['addr'])
      L.LDP(L.local_MR['seq_step[123]']['name'], L.local_MR['seq_step[123]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool, posture = L.FB_setRobotParam(227.146, -10.351, 62.285, 0.0, 0.0, -32.643, 100.0, 100.0, 100.0, 0.1, 0.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, 60, program_override)
        RAC.send_command(f'moveAbsolutePtp({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {json.dumps({'TOOL': 1, 'USER': 1, 'POSTURE': posture, 'VEL': vel, 'ACC': acc, 'DEC': dec})})')
      L.LD(L.local_MR['seq_step[123]']['name'], L.local_MR['seq_step[123]']['addr'])
      L.ANB(L.local_MR['seq_step[1123]']['name'], L.local_MR['seq_step[1123]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {dist})')
      L.LD(L.local_MR['seq_step[123]']['name'], L.local_MR['seq_step[123]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[123]']['addr'], 0.0)
      L.LD(L.local_MR['seq_step[123]']['name'], L.local_MR['seq_step[123]']['addr'])
      L.OUT(L.local_MR['robot_busy[123]']['name'], L.local_MR['robot_busy[123]']['addr'])

      #;Process:set_speed@127
      L.LD(L.local_MR['seq_step[1123]']['name'], L.local_MR['seq_step[1123]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[124]']['name'], L.local_MR['seq_step_reset1[124]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1124]']['name'], L.local_MR['seq_step[1124]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[124]']['name'], L.local_MR['seq_step[124]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.ANPB(L.local_MR['seq_step[124]']['name'], L.local_MR['seq_step[124]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1124]']['name'], L.local_MR['seq_step[1124]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1124]']['name'], L.local_MR['seq_step[1124]']['addr'])
      #;Post-Process:set_speed@127
      #;action:set_speed@127
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[124]']['name'], L.local_MR['seq_step[124]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[123]']['name'], L.local_MR['seq_step_reset1[123]']['addr'])
      L.LDP(L.local_MR['seq_step[124]']['name'], L.local_MR['seq_step[124]']['addr'])
      if (L.aax & L.iix):
        program_override = 100

      #;Process:moveP@128
      L.LD(L.local_MR['seq_step[1124]']['name'], L.local_MR['seq_step[1124]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[125]']['name'], L.local_MR['seq_step_reset1[125]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1125]']['name'], L.local_MR['seq_step[1125]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[125]']['name'], L.local_MR['seq_step[125]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[125]']['name'], L.local_T['move_static_timer[125]']['addr'])
      L.ANPB(L.local_MR['seq_step[125]']['name'], L.local_MR['seq_step[125]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1125]']['name'], L.local_MR['seq_step[1125]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1125]']['name'], L.local_MR['seq_step[1125]']['addr'])
      #;Post-Process:moveP@128
      #;timeout:moveP@128
      L.LD(L.local_MR['seq_step[125]']['name'], L.local_MR['seq_step[125]']['addr'])
      L.TMS(L.local_T['block_timeout[125]']['addr'], 60000000)
      L.LDP(L.local_T['block_timeout[125]']['name'], L.local_T['block_timeout[125]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+125, message='moveP@128:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+125, error_yaml=error_yaml)
      #;error:moveP@128
      L.LD(L.local_MR['seq_step[125]']['name'], L.local_MR['seq_step[125]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+125, message=f"moveP@128:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+125, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+125, message='moveP@128:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+125, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+125, message='moveP@128:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+125, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@128
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[125]']['name'], L.local_MR['seq_step[125]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[124]']['name'], L.local_MR['seq_step_reset1[124]']['addr'])
      L.LDP(L.local_MR['seq_step[125]']['name'], L.local_MR['seq_step[125]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool, posture = L.FB_setRobotParam(227.146, -10.351, 62.285, 0.0, 0.0, -32.643, 100.0, 100.0, 100.0, 0.1, 0.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, 60, program_override)
        RAC.send_command(f'moveAbsolutePtp({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {json.dumps({'TOOL': 1, 'USER': 1, 'POSTURE': posture, 'VEL': vel, 'ACC': acc, 'DEC': dec})})')
      L.LD(L.local_MR['seq_step[125]']['name'], L.local_MR['seq_step[125]']['addr'])
      L.ANB(L.local_MR['seq_step[1125]']['name'], L.local_MR['seq_step[1125]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {dist})')
      L.LD(L.local_MR['seq_step[125]']['name'], L.local_MR['seq_step[125]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[125]']['addr'], 0.0)
      L.LD(L.local_MR['seq_step[125]']['name'], L.local_MR['seq_step[125]']['addr'])
      L.OUT(L.local_MR['robot_busy[125]']['name'], L.local_MR['robot_busy[125]']['addr'])

      #;Process:procedures_callnoreturn@129
      L.LD(L.local_MR['seq_step[1125]']['name'], L.local_MR['seq_step[1125]']['addr'])
      L.MPS()
      L.LDB(L.local_MR['seq_step[1126]']['name'], L.local_MR['seq_step[1126]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[126]']['name'], L.local_MR['seq_step[126]']['addr'])
      L.MPP()
      L.LD(L.local_MR['seq_step[1030]']['name'], L.local_MR['seq_step[1030]']['addr'])
      L.ANPB(L.local_MR['seq_step[126]']['name'], L.local_MR['seq_step[126]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1126]']['name'], L.local_MR['seq_step[1126]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1126]']['name'], L.local_MR['seq_step[1126]']['addr'])
      #;Post-Process:procedures_callnoreturn@129
      #;action:procedures_callnoreturn@129
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[126]']['name'], L.local_MR['seq_step[126]']['addr'])
      L.AND(L.local_MR['seq_step[26]']['name'], L.local_MR['seq_step[26]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[125]']['name'], L.local_MR['seq_step_reset1[125]']['addr'])

      #;Process:moveP@130
      L.LD(L.local_MR['seq_step[1126]']['name'], L.local_MR['seq_step[1126]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[127]']['name'], L.local_MR['seq_step_reset1[127]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1127]']['name'], L.local_MR['seq_step[1127]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[127]']['name'], L.local_MR['seq_step[127]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[127]']['name'], L.local_T['move_static_timer[127]']['addr'])
      L.ANPB(L.local_MR['seq_step[127]']['name'], L.local_MR['seq_step[127]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1127]']['name'], L.local_MR['seq_step[1127]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1127]']['name'], L.local_MR['seq_step[1127]']['addr'])
      #;Post-Process:moveP@130
      #;timeout:moveP@130
      L.LD(L.local_MR['seq_step[127]']['name'], L.local_MR['seq_step[127]']['addr'])
      L.TMS(L.local_T['block_timeout[127]']['addr'], 60000000)
      L.LDP(L.local_T['block_timeout[127]']['name'], L.local_T['block_timeout[127]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+127, message='moveP@130:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+127, error_yaml=error_yaml)
      #;error:moveP@130
      L.LD(L.local_MR['seq_step[127]']['name'], L.local_MR['seq_step[127]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+127, message=f"moveP@130:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+127, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+127, message='moveP@130:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+127, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+127, message='moveP@130:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+127, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@130
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[127]']['name'], L.local_MR['seq_step[127]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[126]']['name'], L.local_MR['seq_step_reset1[126]']['addr'])
      L.LDP(L.local_MR['seq_step[127]']['name'], L.local_MR['seq_step[127]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool, posture = L.FB_setRobotParam(227.146, -10.351, 62.285, 0.0, 0.0, -32.643, 100.0, 100.0, 100.0, 0.1, 0.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, 60, program_override)
        RAC.send_command(f'moveAbsolutePtp({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {json.dumps({'TOOL': 1, 'USER': 1, 'POSTURE': posture, 'VEL': vel, 'ACC': acc, 'DEC': dec})})')
      L.LD(L.local_MR['seq_step[127]']['name'], L.local_MR['seq_step[127]']['addr'])
      L.ANB(L.local_MR['seq_step[1127]']['name'], L.local_MR['seq_step[1127]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {dist})')
      L.LD(L.local_MR['seq_step[127]']['name'], L.local_MR['seq_step[127]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[127]']['addr'], 0.0)
      L.LD(L.local_MR['seq_step[127]']['name'], L.local_MR['seq_step[127]']['addr'])
      L.OUT(L.local_MR['robot_busy[127]']['name'], L.local_MR['robot_busy[127]']['addr'])

      #;Process:set_speed@131
      L.LD(L.local_MR['seq_step[1127]']['name'], L.local_MR['seq_step[1127]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[128]']['name'], L.local_MR['seq_step_reset1[128]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1128]']['name'], L.local_MR['seq_step[1128]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[128]']['name'], L.local_MR['seq_step[128]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.ANPB(L.local_MR['seq_step[128]']['name'], L.local_MR['seq_step[128]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1128]']['name'], L.local_MR['seq_step[1128]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1128]']['name'], L.local_MR['seq_step[1128]']['addr'])
      #;Post-Process:set_speed@131
      #;action:set_speed@131
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[128]']['name'], L.local_MR['seq_step[128]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[127]']['name'], L.local_MR['seq_step_reset1[127]']['addr'])
      L.LDP(L.local_MR['seq_step[128]']['name'], L.local_MR['seq_step[128]']['addr'])
      if (L.aax & L.iix):
        program_override = 100

      #;Process:moveP@132
      L.LD(L.local_MR['seq_step[1128]']['name'], L.local_MR['seq_step[1128]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[129]']['name'], L.local_MR['seq_step_reset1[129]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1129]']['name'], L.local_MR['seq_step[1129]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[129]']['name'], L.local_MR['seq_step[129]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[129]']['name'], L.local_T['move_static_timer[129]']['addr'])
      L.ANPB(L.local_MR['seq_step[129]']['name'], L.local_MR['seq_step[129]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1129]']['name'], L.local_MR['seq_step[1129]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1129]']['name'], L.local_MR['seq_step[1129]']['addr'])
      #;Post-Process:moveP@132
      #;timeout:moveP@132
      L.LD(L.local_MR['seq_step[129]']['name'], L.local_MR['seq_step[129]']['addr'])
      L.TMS(L.local_T['block_timeout[129]']['addr'], 60000000)
      L.LDP(L.local_T['block_timeout[129]']['name'], L.local_T['block_timeout[129]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+129, message='moveP@132:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+129, error_yaml=error_yaml)
      #;error:moveP@132
      L.LD(L.local_MR['seq_step[129]']['name'], L.local_MR['seq_step[129]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+129, message=f"moveP@132:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+129, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+129, message='moveP@132:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+129, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+129, message='moveP@132:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+129, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@132
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[129]']['name'], L.local_MR['seq_step[129]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[128]']['name'], L.local_MR['seq_step_reset1[128]']['addr'])
      L.LDP(L.local_MR['seq_step[129]']['name'], L.local_MR['seq_step[129]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool, posture = L.FB_setRobotParam(227.146, -10.351, 62.285, 0.0, 0.0, -32.643, 100.0, 100.0, 100.0, 0.1, 0.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, 60, program_override)
        RAC.send_command(f'moveAbsolutePtp({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {json.dumps({'TOOL': 1, 'USER': 1, 'POSTURE': posture, 'VEL': vel, 'ACC': acc, 'DEC': dec})})')
      L.LD(L.local_MR['seq_step[129]']['name'], L.local_MR['seq_step[129]']['addr'])
      L.ANB(L.local_MR['seq_step[1129]']['name'], L.local_MR['seq_step[1129]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {dist})')
      L.LD(L.local_MR['seq_step[129]']['name'], L.local_MR['seq_step[129]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[129]']['addr'], 0.0)
      L.LD(L.local_MR['seq_step[129]']['name'], L.local_MR['seq_step[129]']['addr'])
      L.OUT(L.local_MR['robot_busy[129]']['name'], L.local_MR['robot_busy[129]']['addr'])

      #;Process:return@133
      L.LD(L.local_MR['seq_step[1129]']['name'], L.local_MR['seq_step[1129]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[130]']['name'], L.local_MR['seq_step_reset1[130]']['addr'])
      L.MPS()
      L.ANB(L.local_MR['seq_step[1130]']['name'], L.local_MR['seq_step[1130]']['addr'])
      L.OUT(L.local_MR['seq_step[130]']['name'], L.local_MR['seq_step[130]']['addr'])
      L.MPP()
      L.LDPB(L.local_MR['seq_step[130]']['name'], L.local_MR['seq_step[130]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1130]']['name'], L.local_MR['seq_step[1130]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1130]']['name'], L.local_MR['seq_step[1130]']['addr'])
      #;Post-Process:return@133
      #;action:return@133
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[130]']['name'], L.local_MR['seq_step[130]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[129]']['name'], L.local_MR['seq_step_reset1[129]']['addr'])
      L.LDP(L.local_MR['seq_step[130]']['name'], L.local_MR['seq_step[130]']['addr'])
      if (L.aax & L.iix):
        elapsed_time = int((time.perf_counter() - start_time) * 1000)
        L.EM_relay[2020:2020+len(helper.int32_to_uint16s(elapsed_time))] = helper.int32_to_uint16s(elapsed_time)


      #;Process:procedures_defnoreturn@134
      L.LD(L.local_MR['seq_step[22]']['name'], L.local_MR['seq_step[22]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[131]']['name'], L.local_MR['seq_step_reset1[131]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1131]']['name'], L.local_MR['seq_step[1131]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[131]']['name'], L.local_MR['seq_step[131]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.ANPB(L.local_MR['seq_step[131]']['name'], L.local_MR['seq_step[131]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1131]']['name'], L.local_MR['seq_step[1131]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1131]']['name'], L.local_MR['seq_step[1131]']['addr'])
      #;Post-Process:procedures_defnoreturn@134

      #;Process:moveP@135
      L.LD(L.local_MR['seq_step[1131]']['name'], L.local_MR['seq_step[1131]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[132]']['name'], L.local_MR['seq_step_reset1[132]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1132]']['name'], L.local_MR['seq_step[1132]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[132]']['name'], L.local_MR['seq_step[132]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[132]']['name'], L.local_T['move_static_timer[132]']['addr'])
      L.ANPB(L.local_MR['seq_step[132]']['name'], L.local_MR['seq_step[132]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1132]']['name'], L.local_MR['seq_step[1132]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1132]']['name'], L.local_MR['seq_step[1132]']['addr'])
      #;Post-Process:moveP@135
      #;timeout:moveP@135
      L.LD(L.local_MR['seq_step[132]']['name'], L.local_MR['seq_step[132]']['addr'])
      L.TMS(L.local_T['block_timeout[132]']['addr'], 60000000)
      L.LDP(L.local_T['block_timeout[132]']['name'], L.local_T['block_timeout[132]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+132, message='moveP@135:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+132, error_yaml=error_yaml)
      #;error:moveP@135
      L.LD(L.local_MR['seq_step[132]']['name'], L.local_MR['seq_step[132]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+132, message=f"moveP@135:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+132, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+132, message='moveP@135:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+132, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+132, message='moveP@135:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+132, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@135
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[132]']['name'], L.local_MR['seq_step[132]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[131]']['name'], L.local_MR['seq_step_reset1[131]']['addr'])
      L.LDP(L.local_MR['seq_step[132]']['name'], L.local_MR['seq_step[132]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool, posture = L.FB_setRobotParam(227.146, -10.351, 62.285, 0.0, 0.0, -32.643, 100.0, 100.0, 100.0, 0.1, 0.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, 60, program_override)
        RAC.send_command(f'moveAbsolutePtp({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {json.dumps({'TOOL': 1, 'USER': 1, 'POSTURE': posture, 'VEL': vel, 'ACC': acc, 'DEC': dec})})')
      L.LD(L.local_MR['seq_step[132]']['name'], L.local_MR['seq_step[132]']['addr'])
      L.ANB(L.local_MR['seq_step[1132]']['name'], L.local_MR['seq_step[1132]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {dist})')
      L.LD(L.local_MR['seq_step[132]']['name'], L.local_MR['seq_step[132]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[132]']['addr'], 0.0)
      L.LD(L.local_MR['seq_step[132]']['name'], L.local_MR['seq_step[132]']['addr'])
      L.OUT(L.local_MR['robot_busy[132]']['name'], L.local_MR['robot_busy[132]']['addr'])

      #;Process:moveP@136
      L.LD(L.local_MR['seq_step[1132]']['name'], L.local_MR['seq_step[1132]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[133]']['name'], L.local_MR['seq_step_reset1[133]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1133]']['name'], L.local_MR['seq_step[1133]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[133]']['name'], L.local_MR['seq_step[133]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[133]']['name'], L.local_T['move_static_timer[133]']['addr'])
      L.ANPB(L.local_MR['seq_step[133]']['name'], L.local_MR['seq_step[133]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1133]']['name'], L.local_MR['seq_step[1133]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1133]']['name'], L.local_MR['seq_step[1133]']['addr'])
      #;Post-Process:moveP@136
      #;timeout:moveP@136
      L.LD(L.local_MR['seq_step[133]']['name'], L.local_MR['seq_step[133]']['addr'])
      L.TMS(L.local_T['block_timeout[133]']['addr'], 60000000)
      L.LDP(L.local_T['block_timeout[133]']['name'], L.local_T['block_timeout[133]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+133, message='moveP@136:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+133, error_yaml=error_yaml)
      #;error:moveP@136
      L.LD(L.local_MR['seq_step[133]']['name'], L.local_MR['seq_step[133]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+133, message=f"moveP@136:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+133, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+133, message='moveP@136:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+133, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+133, message='moveP@136:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+133, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@136
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[133]']['name'], L.local_MR['seq_step[133]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[132]']['name'], L.local_MR['seq_step_reset1[132]']['addr'])
      L.LDP(L.local_MR['seq_step[133]']['name'], L.local_MR['seq_step[133]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool, posture = L.FB_setRobotParam(227.146, -10.351, 62.285, 0.0, 0.0, -32.643, 100.0, 100.0, 100.0, 0.1, 0.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, 60, program_override)
        RAC.send_command(f'moveAbsolutePtp({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {json.dumps({'TOOL': 1, 'USER': 1, 'POSTURE': posture, 'VEL': vel, 'ACC': acc, 'DEC': dec})})')
      L.LD(L.local_MR['seq_step[133]']['name'], L.local_MR['seq_step[133]']['addr'])
      L.ANB(L.local_MR['seq_step[1133]']['name'], L.local_MR['seq_step[1133]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {dist})')
      L.LD(L.local_MR['seq_step[133]']['name'], L.local_MR['seq_step[133]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[133]']['addr'], 0.0)
      L.LD(L.local_MR['seq_step[133]']['name'], L.local_MR['seq_step[133]']['addr'])
      L.OUT(L.local_MR['robot_busy[133]']['name'], L.local_MR['robot_busy[133]']['addr'])

      #;Process:procedures_callnoreturn@137
      L.LD(L.local_MR['seq_step[1133]']['name'], L.local_MR['seq_step[1133]']['addr'])
      L.MPS()
      L.LDB(L.local_MR['seq_step[1134]']['name'], L.local_MR['seq_step[1134]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[134]']['name'], L.local_MR['seq_step[134]']['addr'])
      L.MPP()
      L.LD(L.local_MR['seq_step[1040]']['name'], L.local_MR['seq_step[1040]']['addr'])
      L.ANPB(L.local_MR['seq_step[134]']['name'], L.local_MR['seq_step[134]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1134]']['name'], L.local_MR['seq_step[1134]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1134]']['name'], L.local_MR['seq_step[1134]']['addr'])
      #;Post-Process:procedures_callnoreturn@137
      #;action:procedures_callnoreturn@137
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[134]']['name'], L.local_MR['seq_step[134]']['addr'])
      L.AND(L.local_MR['seq_step[36]']['name'], L.local_MR['seq_step[36]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[133]']['name'], L.local_MR['seq_step_reset1[133]']['addr'])

      #;Process:set_speed@138
      L.LD(L.local_MR['seq_step[1134]']['name'], L.local_MR['seq_step[1134]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[135]']['name'], L.local_MR['seq_step_reset1[135]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1135]']['name'], L.local_MR['seq_step[1135]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[135]']['name'], L.local_MR['seq_step[135]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.ANPB(L.local_MR['seq_step[135]']['name'], L.local_MR['seq_step[135]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1135]']['name'], L.local_MR['seq_step[1135]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1135]']['name'], L.local_MR['seq_step[1135]']['addr'])
      #;Post-Process:set_speed@138
      #;action:set_speed@138
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[135]']['name'], L.local_MR['seq_step[135]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[134]']['name'], L.local_MR['seq_step_reset1[134]']['addr'])
      L.LDP(L.local_MR['seq_step[135]']['name'], L.local_MR['seq_step[135]']['addr'])
      if (L.aax & L.iix):
        program_override = 100

      #;Process:moveP@139
      L.LD(L.local_MR['seq_step[1135]']['name'], L.local_MR['seq_step[1135]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[136]']['name'], L.local_MR['seq_step_reset1[136]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1136]']['name'], L.local_MR['seq_step[1136]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[136]']['name'], L.local_MR['seq_step[136]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[136]']['name'], L.local_T['move_static_timer[136]']['addr'])
      L.ANPB(L.local_MR['seq_step[136]']['name'], L.local_MR['seq_step[136]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1136]']['name'], L.local_MR['seq_step[1136]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1136]']['name'], L.local_MR['seq_step[1136]']['addr'])
      #;Post-Process:moveP@139
      #;timeout:moveP@139
      L.LD(L.local_MR['seq_step[136]']['name'], L.local_MR['seq_step[136]']['addr'])
      L.TMS(L.local_T['block_timeout[136]']['addr'], 60000000)
      L.LDP(L.local_T['block_timeout[136]']['name'], L.local_T['block_timeout[136]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+136, message='moveP@139:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+136, error_yaml=error_yaml)
      #;error:moveP@139
      L.LD(L.local_MR['seq_step[136]']['name'], L.local_MR['seq_step[136]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+136, message=f"moveP@139:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+136, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+136, message='moveP@139:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+136, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+136, message='moveP@139:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+136, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@139
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[136]']['name'], L.local_MR['seq_step[136]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[135]']['name'], L.local_MR['seq_step_reset1[135]']['addr'])
      L.LDP(L.local_MR['seq_step[136]']['name'], L.local_MR['seq_step[136]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool, posture = L.FB_setRobotParam(227.146, -10.351, 62.285, 0.0, 0.0, -32.643, 100.0, 100.0, 100.0, 0.1, 0.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, 60, program_override)
        RAC.send_command(f'moveAbsolutePtp({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {json.dumps({'TOOL': 1, 'USER': 1, 'POSTURE': posture, 'VEL': vel, 'ACC': acc, 'DEC': dec})})')
      L.LD(L.local_MR['seq_step[136]']['name'], L.local_MR['seq_step[136]']['addr'])
      L.ANB(L.local_MR['seq_step[1136]']['name'], L.local_MR['seq_step[1136]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {dist})')
      L.LD(L.local_MR['seq_step[136]']['name'], L.local_MR['seq_step[136]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[136]']['addr'], 0.0)
      L.LD(L.local_MR['seq_step[136]']['name'], L.local_MR['seq_step[136]']['addr'])
      L.OUT(L.local_MR['robot_busy[136]']['name'], L.local_MR['robot_busy[136]']['addr'])

      #;Process:procedures_callnoreturn@140
      L.LD(L.local_MR['seq_step[1136]']['name'], L.local_MR['seq_step[1136]']['addr'])
      L.MPS()
      L.LDB(L.local_MR['seq_step[1137]']['name'], L.local_MR['seq_step[1137]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[137]']['name'], L.local_MR['seq_step[137]']['addr'])
      L.MPP()
      L.LD(L.local_MR['seq_step[1045]']['name'], L.local_MR['seq_step[1045]']['addr'])
      L.ANPB(L.local_MR['seq_step[137]']['name'], L.local_MR['seq_step[137]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1137]']['name'], L.local_MR['seq_step[1137]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1137]']['name'], L.local_MR['seq_step[1137]']['addr'])
      #;Post-Process:procedures_callnoreturn@140
      #;action:procedures_callnoreturn@140
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[137]']['name'], L.local_MR['seq_step[137]']['addr'])
      L.AND(L.local_MR['seq_step[41]']['name'], L.local_MR['seq_step[41]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[136]']['name'], L.local_MR['seq_step_reset1[136]']['addr'])

      #;Process:set_speed@141
      L.LD(L.local_MR['seq_step[1137]']['name'], L.local_MR['seq_step[1137]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[138]']['name'], L.local_MR['seq_step_reset1[138]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1138]']['name'], L.local_MR['seq_step[1138]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[138]']['name'], L.local_MR['seq_step[138]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.ANPB(L.local_MR['seq_step[138]']['name'], L.local_MR['seq_step[138]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1138]']['name'], L.local_MR['seq_step[1138]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1138]']['name'], L.local_MR['seq_step[1138]']['addr'])
      #;Post-Process:set_speed@141
      #;action:set_speed@141
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[138]']['name'], L.local_MR['seq_step[138]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[137]']['name'], L.local_MR['seq_step_reset1[137]']['addr'])
      L.LDP(L.local_MR['seq_step[138]']['name'], L.local_MR['seq_step[138]']['addr'])
      if (L.aax & L.iix):
        program_override = 100

      #;Process:moveP@142
      L.LD(L.local_MR['seq_step[1138]']['name'], L.local_MR['seq_step[1138]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[139]']['name'], L.local_MR['seq_step_reset1[139]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1139]']['name'], L.local_MR['seq_step[1139]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[139]']['name'], L.local_MR['seq_step[139]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[139]']['name'], L.local_T['move_static_timer[139]']['addr'])
      L.ANPB(L.local_MR['seq_step[139]']['name'], L.local_MR['seq_step[139]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1139]']['name'], L.local_MR['seq_step[1139]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1139]']['name'], L.local_MR['seq_step[1139]']['addr'])
      #;Post-Process:moveP@142
      #;timeout:moveP@142
      L.LD(L.local_MR['seq_step[139]']['name'], L.local_MR['seq_step[139]']['addr'])
      L.TMS(L.local_T['block_timeout[139]']['addr'], 60000000)
      L.LDP(L.local_T['block_timeout[139]']['name'], L.local_T['block_timeout[139]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+139, message='moveP@142:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+139, error_yaml=error_yaml)
      #;error:moveP@142
      L.LD(L.local_MR['seq_step[139]']['name'], L.local_MR['seq_step[139]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+139, message=f"moveP@142:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+139, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+139, message='moveP@142:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+139, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+139, message='moveP@142:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+139, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@142
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[139]']['name'], L.local_MR['seq_step[139]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[138]']['name'], L.local_MR['seq_step_reset1[138]']['addr'])
      L.LDP(L.local_MR['seq_step[139]']['name'], L.local_MR['seq_step[139]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool, posture = L.FB_setRobotParam(227.146, -10.351, 62.285, 0.0, 0.0, -32.643, 100.0, 100.0, 100.0, 0.1, 0.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, 60, program_override)
        RAC.send_command(f'moveAbsolutePtp({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {json.dumps({'TOOL': 1, 'USER': 1, 'POSTURE': posture, 'VEL': vel, 'ACC': acc, 'DEC': dec})})')
      L.LD(L.local_MR['seq_step[139]']['name'], L.local_MR['seq_step[139]']['addr'])
      L.ANB(L.local_MR['seq_step[1139]']['name'], L.local_MR['seq_step[1139]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {dist})')
      L.LD(L.local_MR['seq_step[139]']['name'], L.local_MR['seq_step[139]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[139]']['addr'], 0.0)
      L.LD(L.local_MR['seq_step[139]']['name'], L.local_MR['seq_step[139]']['addr'])
      L.OUT(L.local_MR['robot_busy[139]']['name'], L.local_MR['robot_busy[139]']['addr'])

      #;Process:moveP@143
      L.LD(L.local_MR['seq_step[1139]']['name'], L.local_MR['seq_step[1139]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[140]']['name'], L.local_MR['seq_step_reset1[140]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1140]']['name'], L.local_MR['seq_step[1140]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[140]']['name'], L.local_MR['seq_step[140]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[140]']['name'], L.local_T['move_static_timer[140]']['addr'])
      L.ANPB(L.local_MR['seq_step[140]']['name'], L.local_MR['seq_step[140]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1140]']['name'], L.local_MR['seq_step[1140]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1140]']['name'], L.local_MR['seq_step[1140]']['addr'])
      #;Post-Process:moveP@143
      #;timeout:moveP@143
      L.LD(L.local_MR['seq_step[140]']['name'], L.local_MR['seq_step[140]']['addr'])
      L.TMS(L.local_T['block_timeout[140]']['addr'], 60000000)
      L.LDP(L.local_T['block_timeout[140]']['name'], L.local_T['block_timeout[140]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+140, message='moveP@143:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+140, error_yaml=error_yaml)
      #;error:moveP@143
      L.LD(L.local_MR['seq_step[140]']['name'], L.local_MR['seq_step[140]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+140, message=f"moveP@143:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+140, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+140, message='moveP@143:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+140, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+140, message='moveP@143:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+140, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@143
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[140]']['name'], L.local_MR['seq_step[140]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[139]']['name'], L.local_MR['seq_step_reset1[139]']['addr'])
      L.LDP(L.local_MR['seq_step[140]']['name'], L.local_MR['seq_step[140]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool, posture = L.FB_setRobotParam(227.146, -10.351, 62.285, 0.0, 0.0, -32.643, 100.0, 100.0, 100.0, 0.1, 0.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, 60, program_override)
        RAC.send_command(f'moveAbsolutePtp({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {json.dumps({'TOOL': 1, 'USER': 1, 'POSTURE': posture, 'VEL': vel, 'ACC': acc, 'DEC': dec})})')
      L.LD(L.local_MR['seq_step[140]']['name'], L.local_MR['seq_step[140]']['addr'])
      L.ANB(L.local_MR['seq_step[1140]']['name'], L.local_MR['seq_step[1140]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {dist})')
      L.LD(L.local_MR['seq_step[140]']['name'], L.local_MR['seq_step[140]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[140]']['addr'], 0.0)
      L.LD(L.local_MR['seq_step[140]']['name'], L.local_MR['seq_step[140]']['addr'])
      L.OUT(L.local_MR['robot_busy[140]']['name'], L.local_MR['robot_busy[140]']['addr'])

      #;Process:return@144
      L.LD(L.local_MR['seq_step[1140]']['name'], L.local_MR['seq_step[1140]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[141]']['name'], L.local_MR['seq_step_reset1[141]']['addr'])
      L.MPS()
      L.ANB(L.local_MR['seq_step[1141]']['name'], L.local_MR['seq_step[1141]']['addr'])
      L.OUT(L.local_MR['seq_step[141]']['name'], L.local_MR['seq_step[141]']['addr'])
      L.MPP()
      L.LDPB(L.local_MR['seq_step[141]']['name'], L.local_MR['seq_step[141]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1141]']['name'], L.local_MR['seq_step[1141]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1141]']['name'], L.local_MR['seq_step[1141]']['addr'])
      #;Post-Process:return@144
      #;action:return@144
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[141]']['name'], L.local_MR['seq_step[141]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[140]']['name'], L.local_MR['seq_step_reset1[140]']['addr'])
      L.LDP(L.local_MR['seq_step[141]']['name'], L.local_MR['seq_step[141]']['addr'])
      if (L.aax & L.iix):
        elapsed_time = int((time.perf_counter() - start_time) * 1000)
        L.EM_relay[2020:2020+len(helper.int32_to_uint16s(elapsed_time))] = helper.int32_to_uint16s(elapsed_time)


      #;Process:procedures_defnoreturn@145
      L.LD(L.local_MR['seq_step[24]']['name'], L.local_MR['seq_step[24]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[142]']['name'], L.local_MR['seq_step_reset1[142]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1142]']['name'], L.local_MR['seq_step[1142]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[142]']['name'], L.local_MR['seq_step[142]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.ANPB(L.local_MR['seq_step[142]']['name'], L.local_MR['seq_step[142]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1142]']['name'], L.local_MR['seq_step[1142]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1142]']['name'], L.local_MR['seq_step[1142]']['addr'])
      #;Post-Process:procedures_defnoreturn@145

      #;Process:moveP@146
      L.LD(L.local_MR['seq_step[1142]']['name'], L.local_MR['seq_step[1142]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[143]']['name'], L.local_MR['seq_step_reset1[143]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1143]']['name'], L.local_MR['seq_step[1143]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[143]']['name'], L.local_MR['seq_step[143]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[143]']['name'], L.local_T['move_static_timer[143]']['addr'])
      L.ANPB(L.local_MR['seq_step[143]']['name'], L.local_MR['seq_step[143]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1143]']['name'], L.local_MR['seq_step[1143]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1143]']['name'], L.local_MR['seq_step[1143]']['addr'])
      #;Post-Process:moveP@146
      #;timeout:moveP@146
      L.LD(L.local_MR['seq_step[143]']['name'], L.local_MR['seq_step[143]']['addr'])
      L.TMS(L.local_T['block_timeout[143]']['addr'], 60000000)
      L.LDP(L.local_T['block_timeout[143]']['name'], L.local_T['block_timeout[143]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+143, message='moveP@146:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+143, error_yaml=error_yaml)
      #;error:moveP@146
      L.LD(L.local_MR['seq_step[143]']['name'], L.local_MR['seq_step[143]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+143, message=f"moveP@146:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+143, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+143, message='moveP@146:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+143, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+143, message='moveP@146:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+143, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@146
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[143]']['name'], L.local_MR['seq_step[143]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[142]']['name'], L.local_MR['seq_step_reset1[142]']['addr'])
      L.LDP(L.local_MR['seq_step[143]']['name'], L.local_MR['seq_step[143]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool, posture = L.FB_setRobotParam(227.146, -10.351, 62.285, 0.0, 0.0, -32.643, 100.0, 100.0, 100.0, 0.1, 0.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, 60, program_override)
        RAC.send_command(f'moveAbsolutePtp({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {json.dumps({'TOOL': 1, 'USER': 1, 'POSTURE': posture, 'VEL': vel, 'ACC': acc, 'DEC': dec})})')
      L.LD(L.local_MR['seq_step[143]']['name'], L.local_MR['seq_step[143]']['addr'])
      L.ANB(L.local_MR['seq_step[1143]']['name'], L.local_MR['seq_step[1143]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {dist})')
      L.LD(L.local_MR['seq_step[143]']['name'], L.local_MR['seq_step[143]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[143]']['addr'], 0.0)
      L.LD(L.local_MR['seq_step[143]']['name'], L.local_MR['seq_step[143]']['addr'])
      L.OUT(L.local_MR['robot_busy[143]']['name'], L.local_MR['robot_busy[143]']['addr'])

      #;Process:moveP@147
      L.LD(L.local_MR['seq_step[1143]']['name'], L.local_MR['seq_step[1143]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[144]']['name'], L.local_MR['seq_step_reset1[144]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1144]']['name'], L.local_MR['seq_step[1144]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[144]']['name'], L.local_MR['seq_step[144]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[144]']['name'], L.local_T['move_static_timer[144]']['addr'])
      L.ANPB(L.local_MR['seq_step[144]']['name'], L.local_MR['seq_step[144]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1144]']['name'], L.local_MR['seq_step[1144]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1144]']['name'], L.local_MR['seq_step[1144]']['addr'])
      #;Post-Process:moveP@147
      #;timeout:moveP@147
      L.LD(L.local_MR['seq_step[144]']['name'], L.local_MR['seq_step[144]']['addr'])
      L.TMS(L.local_T['block_timeout[144]']['addr'], 60000000)
      L.LDP(L.local_T['block_timeout[144]']['name'], L.local_T['block_timeout[144]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+144, message='moveP@147:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+144, error_yaml=error_yaml)
      #;error:moveP@147
      L.LD(L.local_MR['seq_step[144]']['name'], L.local_MR['seq_step[144]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+144, message=f"moveP@147:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+144, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+144, message='moveP@147:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+144, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+144, message='moveP@147:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+144, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@147
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[144]']['name'], L.local_MR['seq_step[144]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[143]']['name'], L.local_MR['seq_step_reset1[143]']['addr'])
      L.LDP(L.local_MR['seq_step[144]']['name'], L.local_MR['seq_step[144]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool, posture = L.FB_setRobotParam(227.146, -10.351, 62.285, 0.0, 0.0, -32.643, 100.0, 100.0, 100.0, 0.1, 0.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, 60, program_override)
        RAC.send_command(f'moveAbsolutePtp({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {json.dumps({'TOOL': 1, 'USER': 1, 'POSTURE': posture, 'VEL': vel, 'ACC': acc, 'DEC': dec})})')
      L.LD(L.local_MR['seq_step[144]']['name'], L.local_MR['seq_step[144]']['addr'])
      L.ANB(L.local_MR['seq_step[1144]']['name'], L.local_MR['seq_step[1144]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {dist})')
      L.LD(L.local_MR['seq_step[144]']['name'], L.local_MR['seq_step[144]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[144]']['addr'], 0.0)
      L.LD(L.local_MR['seq_step[144]']['name'], L.local_MR['seq_step[144]']['addr'])
      L.OUT(L.local_MR['robot_busy[144]']['name'], L.local_MR['robot_busy[144]']['addr'])

      #;Process:set_speed@148
      L.LD(L.local_MR['seq_step[1144]']['name'], L.local_MR['seq_step[1144]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[145]']['name'], L.local_MR['seq_step_reset1[145]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1145]']['name'], L.local_MR['seq_step[1145]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[145]']['name'], L.local_MR['seq_step[145]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.ANPB(L.local_MR['seq_step[145]']['name'], L.local_MR['seq_step[145]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1145]']['name'], L.local_MR['seq_step[1145]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1145]']['name'], L.local_MR['seq_step[1145]']['addr'])
      #;Post-Process:set_speed@148
      #;action:set_speed@148
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[145]']['name'], L.local_MR['seq_step[145]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[144]']['name'], L.local_MR['seq_step_reset1[144]']['addr'])
      L.LDP(L.local_MR['seq_step[145]']['name'], L.local_MR['seq_step[145]']['addr'])
      if (L.aax & L.iix):
        program_override = 100

      #;Process:moveP@149
      L.LD(L.local_MR['seq_step[1145]']['name'], L.local_MR['seq_step[1145]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[146]']['name'], L.local_MR['seq_step_reset1[146]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1146]']['name'], L.local_MR['seq_step[1146]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[146]']['name'], L.local_MR['seq_step[146]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[146]']['name'], L.local_T['move_static_timer[146]']['addr'])
      L.ANPB(L.local_MR['seq_step[146]']['name'], L.local_MR['seq_step[146]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1146]']['name'], L.local_MR['seq_step[1146]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1146]']['name'], L.local_MR['seq_step[1146]']['addr'])
      #;Post-Process:moveP@149
      #;timeout:moveP@149
      L.LD(L.local_MR['seq_step[146]']['name'], L.local_MR['seq_step[146]']['addr'])
      L.TMS(L.local_T['block_timeout[146]']['addr'], 60000000)
      L.LDP(L.local_T['block_timeout[146]']['name'], L.local_T['block_timeout[146]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+146, message='moveP@149:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+146, error_yaml=error_yaml)
      #;error:moveP@149
      L.LD(L.local_MR['seq_step[146]']['name'], L.local_MR['seq_step[146]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+146, message=f"moveP@149:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+146, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+146, message='moveP@149:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+146, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+146, message='moveP@149:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+146, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@149
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[146]']['name'], L.local_MR['seq_step[146]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[145]']['name'], L.local_MR['seq_step_reset1[145]']['addr'])
      L.LDP(L.local_MR['seq_step[146]']['name'], L.local_MR['seq_step[146]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool, posture = L.FB_setRobotParam(227.146, -10.351, 62.285, 0.0, 0.0, -32.643, 100.0, 100.0, 100.0, 0.1, 0.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, 60, program_override)
        RAC.send_command(f'moveAbsolutePtp({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {json.dumps({'TOOL': 1, 'USER': 1, 'POSTURE': posture, 'VEL': vel, 'ACC': acc, 'DEC': dec})})')
      L.LD(L.local_MR['seq_step[146]']['name'], L.local_MR['seq_step[146]']['addr'])
      L.ANB(L.local_MR['seq_step[1146]']['name'], L.local_MR['seq_step[1146]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {dist})')
      L.LD(L.local_MR['seq_step[146]']['name'], L.local_MR['seq_step[146]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[146]']['addr'], 0.0)
      L.LD(L.local_MR['seq_step[146]']['name'], L.local_MR['seq_step[146]']['addr'])
      L.OUT(L.local_MR['robot_busy[146]']['name'], L.local_MR['robot_busy[146]']['addr'])

      #;Process:procedures_callnoreturn@150
      L.LD(L.local_MR['seq_step[1146]']['name'], L.local_MR['seq_step[1146]']['addr'])
      L.MPS()
      L.LDB(L.local_MR['seq_step[1147]']['name'], L.local_MR['seq_step[1147]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[147]']['name'], L.local_MR['seq_step[147]']['addr'])
      L.MPP()
      L.LD(L.local_MR['seq_step[1040]']['name'], L.local_MR['seq_step[1040]']['addr'])
      L.ANPB(L.local_MR['seq_step[147]']['name'], L.local_MR['seq_step[147]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1147]']['name'], L.local_MR['seq_step[1147]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1147]']['name'], L.local_MR['seq_step[1147]']['addr'])
      #;Post-Process:procedures_callnoreturn@150
      #;action:procedures_callnoreturn@150
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[147]']['name'], L.local_MR['seq_step[147]']['addr'])
      L.AND(L.local_MR['seq_step[36]']['name'], L.local_MR['seq_step[36]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[146]']['name'], L.local_MR['seq_step_reset1[146]']['addr'])

      #;Process:moveP@151
      L.LD(L.local_MR['seq_step[1147]']['name'], L.local_MR['seq_step[1147]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[148]']['name'], L.local_MR['seq_step_reset1[148]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1148]']['name'], L.local_MR['seq_step[1148]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[148]']['name'], L.local_MR['seq_step[148]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[148]']['name'], L.local_T['move_static_timer[148]']['addr'])
      L.ANPB(L.local_MR['seq_step[148]']['name'], L.local_MR['seq_step[148]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1148]']['name'], L.local_MR['seq_step[1148]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1148]']['name'], L.local_MR['seq_step[1148]']['addr'])
      #;Post-Process:moveP@151
      #;timeout:moveP@151
      L.LD(L.local_MR['seq_step[148]']['name'], L.local_MR['seq_step[148]']['addr'])
      L.TMS(L.local_T['block_timeout[148]']['addr'], 60000000)
      L.LDP(L.local_T['block_timeout[148]']['name'], L.local_T['block_timeout[148]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+148, message='moveP@151:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+148, error_yaml=error_yaml)
      #;error:moveP@151
      L.LD(L.local_MR['seq_step[148]']['name'], L.local_MR['seq_step[148]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+148, message=f"moveP@151:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+148, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+148, message='moveP@151:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+148, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+148, message='moveP@151:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+148, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@151
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[148]']['name'], L.local_MR['seq_step[148]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[147]']['name'], L.local_MR['seq_step_reset1[147]']['addr'])
      L.LDP(L.local_MR['seq_step[148]']['name'], L.local_MR['seq_step[148]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool, posture = L.FB_setRobotParam(227.146, -10.351, 62.285, 0.0, 0.0, -32.643, 100.0, 100.0, 100.0, 0.1, 0.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, 60, program_override)
        RAC.send_command(f'moveAbsolutePtp({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {json.dumps({'TOOL': 1, 'USER': 1, 'POSTURE': posture, 'VEL': vel, 'ACC': acc, 'DEC': dec})})')
      L.LD(L.local_MR['seq_step[148]']['name'], L.local_MR['seq_step[148]']['addr'])
      L.ANB(L.local_MR['seq_step[1148]']['name'], L.local_MR['seq_step[1148]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {dist})')
      L.LD(L.local_MR['seq_step[148]']['name'], L.local_MR['seq_step[148]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[148]']['addr'], 0.0)
      L.LD(L.local_MR['seq_step[148]']['name'], L.local_MR['seq_step[148]']['addr'])
      L.OUT(L.local_MR['robot_busy[148]']['name'], L.local_MR['robot_busy[148]']['addr'])

      #;Process:set_speed@152
      L.LD(L.local_MR['seq_step[1148]']['name'], L.local_MR['seq_step[1148]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[149]']['name'], L.local_MR['seq_step_reset1[149]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1149]']['name'], L.local_MR['seq_step[1149]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[149]']['name'], L.local_MR['seq_step[149]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.ANPB(L.local_MR['seq_step[149]']['name'], L.local_MR['seq_step[149]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1149]']['name'], L.local_MR['seq_step[1149]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1149]']['name'], L.local_MR['seq_step[1149]']['addr'])
      #;Post-Process:set_speed@152
      #;action:set_speed@152
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[149]']['name'], L.local_MR['seq_step[149]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[148]']['name'], L.local_MR['seq_step_reset1[148]']['addr'])
      L.LDP(L.local_MR['seq_step[149]']['name'], L.local_MR['seq_step[149]']['addr'])
      if (L.aax & L.iix):
        program_override = 100

      #;Process:moveP@153
      L.LD(L.local_MR['seq_step[1149]']['name'], L.local_MR['seq_step[1149]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[150]']['name'], L.local_MR['seq_step_reset1[150]']['addr'])
      L.MPS()
      L.LDB(MR, 304)
      L.ANB(L.local_MR['seq_step[1150]']['name'], L.local_MR['seq_step[1150]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[150]']['name'], L.local_MR['seq_step[150]']['addr'])
      L.MPP()
      L.LDB(MR, 304)
      L.AND(robot_status['arrived'])
      L.AND(L.local_T['move_static_timer[150]']['name'], L.local_T['move_static_timer[150]']['addr'])
      L.ANPB(L.local_MR['seq_step[150]']['name'], L.local_MR['seq_step[150]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1150]']['name'], L.local_MR['seq_step[1150]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1150]']['name'], L.local_MR['seq_step[1150]']['addr'])
      #;Post-Process:moveP@153
      #;timeout:moveP@153
      L.LD(L.local_MR['seq_step[150]']['name'], L.local_MR['seq_step[150]']['addr'])
      L.TMS(L.local_T['block_timeout[150]']['addr'], 60000000)
      L.LDP(L.local_T['block_timeout[150]']['name'], L.local_T['block_timeout[150]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        drive.register_error(no=801+150, message='moveP@153:A timeout occurred.', error_yaml=error_yaml)
        drive.raise_error(no=801+150, error_yaml=error_yaml)
      #;error:moveP@153
      L.LD(L.local_MR['seq_step[150]']['name'], L.local_MR['seq_step[150]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):
          drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):
          drive.register_error(no=801+150, message=f"moveP@153:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)
          drive.raise_error(no=801+150, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if ((100.0 == 0) or (100.0 == 0) or (100.0 == 0)):
          drive.register_error(no=801+150, message='moveP@153:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)
          drive.raise_error(no=801+150, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
        if (robot_status['servo'] == False):
          drive.register_error(no=801+150, message='moveP@153:Servo is off.', error_yaml=error_yaml)
          drive.raise_error(no=801+150, error_yaml=error_yaml)
          drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)
      #;action:moveP@153
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[150]']['name'], L.local_MR['seq_step[150]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[149]']['name'], L.local_MR['seq_step_reset1[149]']['addr'])
      L.LDP(L.local_MR['seq_step[150]']['name'], L.local_MR['seq_step[150]']['addr'])
      L.ANB(MR, 501)
      if ((L.aax & L.iix) and (RAC.connected)):
        offset_x = 0
        offset_y = 0
        offset_z = 0
        offset_rx = 0
        offset_ry = 0
        offset_rz = 0
        x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool, posture = L.FB_setRobotParam(227.146, -10.351, 62.285, 0.0, 0.0, -32.643, 100.0, 100.0, 100.0, 0.1, 0.0, 0.0, 0.0, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, 60, program_override)
        RAC.send_command(f'moveAbsolutePtp({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {json.dumps({'TOOL': 1, 'USER': 1, 'POSTURE': posture, 'VEL': vel, 'ACC': acc, 'DEC': dec})})')
      L.LD(L.local_MR['seq_step[150]']['name'], L.local_MR['seq_step[150]']['addr'])
      L.ANB(L.local_MR['seq_step[1150]']['name'], L.local_MR['seq_step[1150]']['addr'])
      if ((L.aax & L.iix) and (RAC.connected)):
        RAC.send_command(f'waitArrive({json.dumps({'X': x, 'Y': y, 'Z': z, 'RX': rx, 'RY': ry, 'RZ': rz})}, {dist})')
      L.LD(L.local_MR['seq_step[150]']['name'], L.local_MR['seq_step[150]']['addr'])
      L.AND(robot_status['arrived'])
      L.TMS(L.local_T['move_static_timer[150]']['addr'], 0.0)
      L.LD(L.local_MR['seq_step[150]']['name'], L.local_MR['seq_step[150]']['addr'])
      L.OUT(L.local_MR['robot_busy[150]']['name'], L.local_MR['robot_busy[150]']['addr'])

      #;Process:return@154
      L.LD(L.local_MR['seq_step[1150]']['name'], L.local_MR['seq_step[1150]']['addr'])
      L.ANB(L.local_MR['seq_step_reset1[151]']['name'], L.local_MR['seq_step_reset1[151]']['addr'])
      L.MPS()
      L.ANB(L.local_MR['seq_step[1151]']['name'], L.local_MR['seq_step[1151]']['addr'])
      L.OUT(L.local_MR['seq_step[151]']['name'], L.local_MR['seq_step[151]']['addr'])
      L.MPP()
      L.LDPB(L.local_MR['seq_step[151]']['name'], L.local_MR['seq_step[151]']['addr'])
      L.LDP(R, 7801)
      L.ORB(R, 7800)
      L.ANL()
      L.OR(L.local_MR['seq_step[1151]']['name'], L.local_MR['seq_step[1151]']['addr'])
      L.ANL()
      L.OUT(L.local_MR['seq_step[1151]']['name'], L.local_MR['seq_step[1151]']['addr'])
      #;Post-Process:return@154
      #;action:return@154
      L.LDP(R, 7802)
      L.AND(L.local_MR['seq_step[151]']['name'], L.local_MR['seq_step[151]']['addr'])
      L.OUT(L.local_MR['seq_step_reset1[150]']['name'], L.local_MR['seq_step_reset1[150]']['addr'])
      L.LDP(L.local_MR['seq_step[151]']['name'], L.local_MR['seq_step[151]']['addr'])
      if (L.aax & L.iix):
        elapsed_time = int((time.perf_counter() - start_time) * 1000)
        L.EM_relay[2020:2020+len(helper.int32_to_uint16s(elapsed_time))] = helper.int32_to_uint16s(elapsed_time)

    except Exception as e:  
      cleanup_device()
      func.cleanup()
      print(e)
      sys.exit(-1)

