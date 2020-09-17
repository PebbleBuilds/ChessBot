# Inverse Kinematics Code
# By KiriBuilds
#
# This code:
# - ingests target positions in the form of a list of 3-tuples
# - outputs motor angles to an Arduino

#!/usr/bin/env python
import rospy, serial, sys, time, struct
from IK_lib import *
from geometry_msgs.msg import Point

class CheckMoving():
    def __init__(self, duration):
        self.duration = duration
        self.last_time = time.time() * 1000

    def start_timing(self):
        self.last_time = time.time() * 1000

    def check_if_done(self):
        if time.time() * 1000 - self.last_time + 500 > self.duration:
            return True
        return False

class IK_Arm():
    def __init__(self, com_port=None, duration=3000):
        self.CMD_SET_BASE = 1
        self.CMD_SET_SHOULDER = 2
        self.CMD_SET_ELBOW = 3
        self.CMD_SET_INTERVAL = 4
        self.CMD_GET_QUEUE_MAX = 5

        self.CFG_CMD_VAL_PLACES = 4

        self.servo_min_996 = 550
        self.servo_max_996 = 2450

        self.init_pos = [0.0,50.0,50.0]
        self.com_port = com_port
        self.duration = duration # in ms
        self.move_checker = CheckMoving(duration)
        self.queue_max = 50
    
        self.d1 = 175 # (in mm)
        self.d2 = 175

        self.ser = None

        self.ser_init()

        if self.ser is not None:
            self.send_cmd(self.CMD_GET_QUEUE_MAX, 0)
            # TODO add a read here to check QUEUE_MAX from arduino
            print("[IK_Node] queue_max set to %d"%self.queue_max)
            self.send_cmd(self.CMD_SET_INTERVAL, duration // self.queue_max)
            print("[IK_Node] serial connected")

    def ser_init(self):
        baud = 2400
        baseports = ['/dev/ttyUSB', '/dev/ttyACM', 'COM', '/dev/tty.usbmodem1234']
        self.ser = None

        while not self.ser:
            for baseport in baseports:
                if self.ser:
                    break
                for i in xrange(0, 64):
                    try:
                        port = baseport + str(i)
                        self.ser = serial.Serial(port, baud, timeout=1)
                        print("Monitor: Opened " + port + '\r')
                        break
                    except:
                        self.ser = None
                        pass

            if not self.ser:
                print("[IK_Node] Couldn't open a serial port.")
    
    def find_intermediate_positions(self, init_pos, final_pos):
        curr_pos = list(init_pos)
        increment = [0] * len(init_pos)
        intermediate_positions = []    
        for idx in range(0, len(init_pos)):
            increment[idx] = (final_pos[idx] - init_pos[idx]) / float(self.queue_max)
        for n in range(0, self.queue_max):
            for idx in range(0, len(init_pos)):
                curr_pos[idx] += increment[idx]
            intermediate_positions.append(list(curr_pos))    
        return intermediate_positions

    def send_cmd(self, cmd_id, cmd_val):
        cmd_id_shift = 10**self.CFG_CMD_VAL_PLACES 
        if cmd_id_shift < cmd_val:
            print("Invalid command value received")
            return None
        cmd = cmd_id_shift * cmd_id + cmd_val
        print("[IK_Node] sending cmd: %d"%cmd)
        if self.ser == None:
            return None
        self.ser.write((str(cmd)+'/').encode())
    
    def callback(self, received_point):
        rospy.loginfo(rospy.get_caller_id() + "I heard %f, %f, %f" %(received_point.x, received_point.y, received_point.z))
    
        final_pos = [received_point.x, received_point.y, received_point.z]

        rospy.loginfo("[IK_Node]Moving from %r to %r"%(self.init_pos, final_pos))
    
        i_positions = self.find_intermediate_positions(self.init_pos, final_pos)
        i_us_list = []
    
        for pos in i_positions:
            arm_angles = cartesian_to_angles(pos, self.d1, self.d2)
            if arm_angles == None:
                rospy.loginfo("[IK_Node] Impossible position")
                return
            i_us_list.append(angles_to_us(arm_angles,self.servo_min_996,self.servo_max_996))
    
        if not self.move_checker.check_if_done():
            rospy.loginfo("[IK_Node] Arm was still moving - new move message ignored")
            return
    
        for i,pos in enumerate(i_us_list):
            rospy.loginfo("[IK_Node] ### Filling Queue Slot %d" %i)
            self.send_cmd(self.CMD_SET_BASE, pos[0])
            self.send_cmd(self.CMD_SET_SHOULDER, pos[1])
            self.send_cmd(self.CMD_SET_ELBOW, pos[2])
        
        self.move_checker.start_timing()
        self.init_pos = final_pos

#ROS stuff down here
def listener(com_port=None):
    # In ROS, nodes are uniquely named. If two nodes with the same
    # name are launched, the previous one is kicked off. The
    # anonymous=True flag means that rospy will choose a unique
    # name for our 'listener' node so that multiple listeners can
    # run simultaneously.
    rospy.init_node('IK', anonymous=True)    

    arm = IK_Arm(com_port)

    rospy.Subscriber("target_positions", Point, arm.callback)
         
    # spin() simply keeps python from exiting until this node is stopped

    while True:
        try:
            bytesToRead = arm.ser.inWaiting() # get the amount of bytes available at the input queue
            if bytesToRead:
                line = arm.ser.read_until() # read the bytes
                print("Arduino: " + line.strip())
        except AttributeError:
            pass
        except KeyboardInterrupt:
            import sys, tty, termios
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old_settings)
            sys.exit(1)
        except Exception as error:
            print(error)
            import sys, tty, termios
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old_settings)
            sys.exit(1)

if __name__ == '__main__':
    try:
        listener("/dev/ttyUSB0")
    except rospy.ROSInterruptException:
        pass