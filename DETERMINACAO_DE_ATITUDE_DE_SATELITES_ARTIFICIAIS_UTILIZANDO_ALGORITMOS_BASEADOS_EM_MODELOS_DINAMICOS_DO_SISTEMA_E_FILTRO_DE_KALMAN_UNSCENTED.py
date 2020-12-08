UNIVERSIDADE FEDERAL DO ABC TRABALHO DE GRADUACAO - ENGENHARIA AEROESPACIAL (CECS)
#ORIENTADOR:      LUIZ DE SIQUEIRA MARTINS FILHO
#ALUNOS:          CAMILA MORAIS MARQUES DE LIMA
#                 DANILO NUNES LIMA

###############################################################################
########################## IMPORT LIBRARIES ###################################
###############################################################################

from scipy.interpolate import interp1d
import numpy as np
import win32com.client
from win32api import GetSystemMetrics
import comtypes
from comtypes.client import CreateObject
import math
from pyquaternion import Quaternion
from scipy.integrate import solve_ivp
import random
import scipy.linalg
import time

###############################################################################
################################# FUNCTIONS ###################################
###############################################################################

## ROTATION MATRIX

def rotmX(theta) :
     
    R_x = np.array([[1,         0,                  0                   ],
                    [0,         math.cos(theta), math.sin(theta) ],
                    [0,         -math.sin(theta), math.cos(theta)  ]
                    ])
 
    return R_x

def rotmY(theta) :
     
    R_y = np.array([[math.cos(theta),    0,      -math.sin(theta)  ],
                    [0,                     1,      0                   ],
                    [math.sin(theta),   0,      math.cos(theta)  ]
                    ])
 
    return R_y

def rotmZ(theta) :
     
    R_z = np.array([[math.cos(theta),    math.sin(theta),    0],
                    [-math.sin(theta),    math.cos(theta),     0],
                    [0,                     0,                      1]
                    ])
 
    return R_z

def skew(x):
    return np.matrix([[0, -x[2], x[1]],
                      [x[2], 0, -x[0]],
                      [-x[1], x[0], 0]])
    
def Omega(w):

    Omega = np.matrix([[0,w[0],w[1],w[2]],
                   [-w[0],0,w[2],-w[1]],
                   [-w[1],-w[2],0,w[0]],
                   [-w[2],w[1],-w[0],0]])
    return Omega
    
def Equations(t,q,w,I_sat,N):

    w = w/(180/np.pi)
    N = np.zeros((3,1))
    I_sat = np.matrix([[Ixx,0,0],[0,Iyy,0],[0,0,Izz]])
    dqdt = (1/2)*np.matmul(Omega(w),q)
    dqdt = ([dqdt[0,0],dqdt[0,1],dqdt[0,2],dqdt[0,3]])
    dwdt = np.matmul((np.linalg.inv(I_sat)),(np.matmul(-skew(np.array([(w[0]/(180/np.pi)),(w[1]/(180/np.pi)),(w[2]/(180/np.pi))])),np.transpose((np.matmul(I_sat,np.array([(-w[0]/(180/np.pi)),(-w[1]/(180/np.pi)),(-w[2]/(180/np.pi))]))))) + np.transpose(N)))
    return dqdt

def ValidateCovarianceMatrix(sig):
    
    eps = 10e-6
    zero = 10e-10
    
    try:
        error = scipy.linalg.cholesky(sig,False,overwrite_a=True)
        sigma = sig
    except:
        print("The covariance matrix is not positive definite!")

        # the covariance matrix is not positive definite!
        v_eigenvalues, v_eigenvectors = scipy.linalg.eig(sig)
        
        for val, vec in zip(v_eigenvalues, v_eigenvectors.T):
            assert np.allclose(np.dot(sig, vec), val * vec)
        
        D = np.diag(vec)
        
        # set any of the eigenvalues that are <= 0 to some small positive value
        for eg in range(0,len(D)):
            if D[eg, eg] <= zero:
                D[eg, eg] = eps

        # recompose the covariance matrix, now it should be positive definite.
        sig = np.matmul(v_eigenvectors,np.matmul(D,np.linalg.inv(v_eigenvectors)))
        
        try:
            error = scipy.linalg.cholesky(sig,False,overwrite_a=True)
            sigma = sig
        except:
            sigma = 0
            print('error again...')
            
    return sigma

def quaternion_multiply(q, p):
    q4, q1, q2, q3 = q
    p4, p1, p2, p3 = p
    
    p_aux = np.matrix([[-q1 * p1 - q2 * p2 - q3 * p3 + q4 * p4],
                     [q1 * p4 + q2 * p3 - q3 * p2 + q4 * p1],
                     [-q1 * p3 + q2 * p4 + q3 * p1 + q4 * p2],
                     [q1 * p2 - q2 * p1 + q3 * p4 + q4 * p3]], dtype=np.float64)
    q_multiply = Quaternion(p_aux)
    return q_multiply
     
def quaternion_complex(q):
    q_complex = Quaternion(vector=-q.vector, scalar=q.scalar)
    return q_complex

def quaternion_norm(q):
    q1, q2, q3, q4 = q
    q_norm = math.sqrt(q1**2 + q2**2 + q3**2 + q4**2)
    return q_norm

def quaternion_inverse(q):
    q_inverse = (quaternion_complex(q))/(quaternion_norm(q)**(2))
    q_inverse= Quaternion(q_inverse)
    return q_inverse

def quaternion_rotation(q,v):
    v = Quaternion(np.vstack([0,v]))
    w = quaternion_multiply(v,q)
    q_rotation = quaternion_multiply(quaternion_complex(q),w)
    return q_rotation

def quaternion_continuity(R):
    epsilon = 0.0001
    epsilon_2 = epsilon**2
    
    ro_2 = (R[0,0]+R[1,1]+R[2,2]+1)*(1/4)
    
    if ro_2 >= epsilon_2:
        ro_til = np.sqrt(ro_2)
        delta_ro_til = (R[2,1]-R[1,2])*(1/4)
        mi_ro_til = (R[0,2]-R[2,0])*(1/4)
        nu_ro_til = (R[1,0]-R[0,2])*(1/4)
        ro_ro_til = ro_2
    else:
        ro_til = epsilon
        delta_ro_til = np.sign(R[2,1]-R[1,2])*(1/2)*epsilon*np.sqrt(R[0,0]-R[1,1]-R[2,2]+1)
        mi_ro_til = np.sign(R[0,2]-R[2,0])*(1/2)*epsilon*np.sqrt(-R[0,0]+R[1,1]-R[2,2]+1)
        nu_ro_til = np.sign(R[1,0]-R[0,2])*(1/2)*epsilon*np.sqrt(-R[0,0]-R[1,1]+R[2,2]+1)
        ro_ro_til = epsilon*np.sqrt(ro_2)
    
    ro_til_star_2 = delta_ro_til**2 + mi_ro_til**2 + nu_ro_til**2 + ro_ro_til**2
    
    delta_2 = (delta_ro_til**2)/(ro_til_star_2)
    mi_2 = (mi_ro_til**2)/(ro_til_star_2)
    nu_2 = (nu_ro_til**2)/(ro_til_star_2)
    ro_2 = (ro_ro_til**2)/(ro_til_star_2)
    
    q = Quaternion(vector=[delta_2,mi_2,nu_2],scalar=ro_2)
    
    return q

def quaternion_antipod(q0,q):
    antipod = q0[0]*q[0] + q0[1]*q[1] + q0[2]*q[2] + q0[3]*q[3]
    if antipod < 0:
        q_antipod = -q
    else:
        q_antipod = q
        
    return q_antipod

###############################################################################
####################### EXTRACT INFORMATION FROM STK ##########################
###############################################################################

# GET REFERENCE TO RUNNING STK INSTANCE
uiApplication = CreateObject("STK11.Application")

uiApplication.Visible=True
uiApplication.UserControl=True

# GET OUR IAgStkObjectRoot INTERFACE
root=uiApplication.Personality2

#Note: When 'root=uiApplication.Personality2' is executed, 
#the comtypes library automatically creates a gen folder that 
#contains STKUtil and STK Objects. After running this at 
#least once on your computer, the following two lines should 
#be moved before the 'uiApplication=CreateObject("STK11.Application")' 
#line for improved performance.  

from comtypes.gen import STKUtil
from comtypes.gen import STKObjects

########################### CREATE A NEW SCENARIO #############################

root.NewScenario("Python_Starter")
scenario         = root.CurrentScenario

###################### SET THE ANALYTICAL TIME PERIOD #########################

scenario2        = scenario.QueryInterface(STKObjects.IAgScenario)
scenario2.SetTimePeriod('7 Dec 2014 10:12:12.5306','7 Dec 2014 18:12:12.5306')
######################## RESET THE ANIMATION TIME #############################

root.Rewind();

################### ADD A TARGET OBJECT TO THE SCENARIO #######################

target           = scenario.Children.New(STKObjects.eTarget,"UFABC");
target2          = target.QueryInterface(STKObjects.IAgTarget)

############### MOVE THE TARGET OBJECT TO A DESIRED LOCATION ##################

target2.Position.AssignGeodetic(-23.6774886,-46.5652192,0)

################## ADD A SATELLITE OBJECT TO THE SCENARIO #####################

satellite        = scenario.Children.New(STKObjects.eSatellite, "CBERS_4_40336")
satellite2       = satellite.QueryInterface(STKObjects.IAgSatellite)

########################## CHANGE THE PROPAGATOR ##############################

satellite2.PropagatorSupportedTypes
satellite2.SetPropagatorType(STKObjects.ePropagatorSGP4)

###################### SET SATELLITE FROM ONLINE SOURCE ########################

satProp = satellite2.Propagator
satProp=satProp.QueryInterface(STKObjects.IAgVePropagatorSGP4)
satProp.CommonTasks.AddSegsFromOnlineSource('40336')    #CBERS-4
satProp.Propagate()

############################### SET TIME STEPS ################################

time_step = 10 #[seconds]

################## EXTRACT INFORMATION FROM THE SCENARIO ######################

#### Cartesian Velocity [J2000] #####

cartVelICRF=satellite.DataProviders("Cartesian Velocity")

cartVelICRF=cartVelICRF.QueryInterface(STKObjects.IAgDataProviderGroup)

cartVelICRF2=cartVelICRF.Group.Item("J2000")

cartVelICRFTimeVar = cartVelICRF2.QueryInterface(STKObjects.IAgDataPrvTimeVar)

rptElements=['Time','x','y','z']

velResultICRF=cartVelICRFTimeVar.ExecElements(scenario2.StartTime,
                                              scenario2.StopTime,time_step,rptElements)

timer=velResultICRF.DataSets.Item(0).GetValues()

xVelocity_ICRF=velResultICRF.DataSets.Item(1).GetValues()
yVelocity_ICRF=velResultICRF.DataSets.Item(2).GetValues()
zVelocity_ICRF=velResultICRF.DataSets.Item(3).GetValues()

##### Vectors(Inertial) [Position] #####

PositionDP = satellite.DataProviders.Item('Vectors(J2000)') #<------- Alterando para J2000

PositionDP2 = PositionDP.QueryInterface(STKObjects.IAgDataProviderGroup)

PositionDP3 = PositionDP2.Group.Item('Position')

PositionDP4 = PositionDP3.QueryInterface(STKObjects.IAgDataPrvTimeVar)

rptElements = ['Time','x','y','z','Magnitude','x/Magnitude','y/Magnitude',
               'z/Magnitude','RightAscension','Declination','Co-Declination',
               'NegativeDeclination','DirectionAngle x','DirectionAngle y',
               'DirectionAngle z','Derivative x','Derivative y','Derivative z',
               'Derivative Magnitude']

PositionDPTimeVar = PositionDP4.ExecElements(scenario2.StartTime,scenario2.StopTime,
                                             time_step, rptElements)

x_Position = PositionDPTimeVar.DataSets.GetDataSetByName('x').GetValues() #[km]
y_Position = PositionDPTimeVar.DataSets.GetDataSetByName('y').GetValues() #[km]
z_Position = PositionDPTimeVar.DataSets.GetDataSetByName('z').GetValues() #[km]
Magnitude_Position = PositionDPTimeVar.DataSets.GetDataSetByName('Magnitude').GetValues() #[km]
xMagnitude_Position = PositionDPTimeVar.DataSets.GetDataSetByName('x/Magnitude').GetValues() 
yMagnitude_Position = PositionDPTimeVar.DataSets.GetDataSetByName('y/Magnitude').GetValues() 
zMagnitude_Position = PositionDPTimeVar.DataSets.GetDataSetByName('z/Magnitude').GetValues()

#### True Anomaly Step [J2000] #####

ClassicalElementsDP=satellite.DataProviders("Classical Elements")

ClassicalElementsDP2=ClassicalElementsDP.QueryInterface(STKObjects.IAgDataProviderGroup)

ClassicalElementsDP3=ClassicalElementsDP2.Group.Item("J2000")

ClassicalElementsDP4 = ClassicalElementsDP3.QueryInterface(STKObjects.IAgDataPrvTimeVar)

rptElements=['Time','Semi-major Axis','Eccentricity','Inclination','RAAN',
             'Arg of Perigee','True Anomaly','Mean Anomaly','Arg of Latitude',
             'Apogee Altitude','Apogee Radius','Perigee Altitude','Perigee Radius',
             'Mean Motion (Revs/Day)','Lon Ascn Node','Eccentric Anomaly',
             'Time Past AN','Time Past Perigee','Period','Longitude of Perigee',
             'Mean Longitude']

ClassicalElementsDPTimeVar=ClassicalElementsDP4.ExecElements(scenario2.StartTime,
                                                             scenario2.StopTime,time_step,rptElements)

SemiMajorAxis_J2000=ClassicalElementsDPTimeVar.DataSets.GetDataSetByName('Semi-major Axis').GetValues() #[km]
Eccentricity_J2000=ClassicalElementsDPTimeVar.DataSets.GetDataSetByName('Eccentricity').GetValues()
Inclination_J2000=ClassicalElementsDPTimeVar.DataSets.GetDataSetByName('Inclination').GetValues() #[degrees]
RAAN_J2000=ClassicalElementsDPTimeVar.DataSets.GetDataSetByName('RAAN').GetValues() #[degrees]
ArgOfPerigee_J2000=ClassicalElementsDPTimeVar.DataSets.GetDataSetByName('Arg of Perigee').GetValues() #[degrees]
TrueAnomaly_J2000=ClassicalElementsDPTimeVar.DataSets.GetDataSetByName('True Anomaly').GetValues() #[degrees]
MeanAnomaly_J2000=ClassicalElementsDPTimeVar.DataSets.GetDataSetByName('Mean Anomaly').GetValues() #[degrees]
ArgOfLatitude_J2000=ClassicalElementsDPTimeVar.DataSets.GetDataSetByName('Arg of Latitude').GetValues() #[degrees]
ApogeeAltitude_J2000=ClassicalElementsDPTimeVar.DataSets.GetDataSetByName('Apogee Altitude').GetValues() #[km]
ApogeeRadius_J2000=ClassicalElementsDPTimeVar.DataSets.GetDataSetByName('Apogee Radius').GetValues() #[km]
PerigeeAltitude_J2000=ClassicalElementsDPTimeVar.DataSets.GetDataSetByName('Perigee Altitude').GetValues() #[km]
PerigeeRadius_J2000=ClassicalElementsDPTimeVar.DataSets.GetDataSetByName('Perigee Radius').GetValues() #[km]
MeanMotion_J2000=ClassicalElementsDPTimeVar.DataSets.GetDataSetByName('Mean Motion (Revs/Day)').GetValues() #[Revolutions/Day]
LonAscnNode_J2000=ClassicalElementsDPTimeVar.DataSets.GetDataSetByName('Lon Ascn Node').GetValues() #[degrees]
EccentricAnomaly_J2000=ClassicalElementsDPTimeVar.DataSets.GetDataSetByName('Eccentric Anomaly').GetValues() #[degrees]
Period_J2000=ClassicalElementsDPTimeVar.DataSets.GetDataSetByName('Period').GetValues() #[secs]
LongitudeOfPerigee_J2000=ClassicalElementsDPTimeVar.DataSets.GetDataSetByName('Longitude of Perigee').GetValues() #[degrees]
MeanLongitude_J2000=ClassicalElementsDPTimeVar.DataSets.GetDataSetByName('Mean Longitude').GetValues() #[degrees]

#### Euler Angles [Seq 313] #####

#From help.agi.com: The attitude of the vehicle (i.e., the rotation between the vehicle's body axes and the vehicle' central body's inertial frame) expressed using Euler angles.
#Euler angles use a sequence of three rotations starting from a reference coordinate frame. The rotations are performed in succession: each rotation is relative to the frame
#resulting from any previous rotations. The sequence of three rotations is indicated by a integer sequence where the X axis is 1, Y axis is 2, and Z axis is 3.
#For example, a 313 sequence uses Z, then the new X, and then finally the newest Z axis.

EulerAnglesDP=satellite.DataProviders("Euler Angles")

EulerAnglesDP2=EulerAnglesDP.QueryInterface(STKObjects.IAgDataProviderGroup)

EulerAnglesDP3=EulerAnglesDP2.Group.Item("Seq 313")

EulerAnglesDP4 = EulerAnglesDP3.QueryInterface(STKObjects.IAgDataPrvTimeVar)

rptElements=['Time','A','B','C','A dot','B dot','C dot']

EulerAnglesDPTimeVar=EulerAnglesDP4.ExecElements(scenario2.StartTime,
                                                 scenario2.StopTime,time_step,rptElements)

precession_angle=EulerAnglesDPTimeVar.DataSets.GetDataSetByName('A').GetValues() #[degrees]
nutation_angle=EulerAnglesDPTimeVar.DataSets.GetDataSetByName('B').GetValues() #[degrees]
spin_angle=EulerAnglesDPTimeVar.DataSets.GetDataSetByName('C').GetValues() #[degrees]

##### Attitude Quaternion Vector #####

#From help.agi.com: The attitude quaternion and angular velocity of the vehicle's body axes computed with respect to the vehicle's central body inertial coordinate system.
#The quaternion components q1, q2, and q3 are the vector components of the quaternion; q4 is the scalar part. The angular velocity is computed as observed from the
#inertial frame and resolved into body components.

AttitudeVectorDP = satellite.DataProviders.Item('Attitude Quaternions')

AttitudeVectorDP2 = AttitudeVectorDP.QueryInterface(STKObjects.IAgDataPrvTimeVar)

rptElements = ['Time','q1','q2','q3','q4','wx','wy','wz','w mag',
               'RightAscension of w','Declination of w']

AttitudeVectorDPTimeVar = AttitudeVectorDP2.ExecElements(scenario2.StartTime,
                                                         scenario2.StopTime, time_step,
                                                         rptElements)

q1_AttitudeVector = AttitudeVectorDPTimeVar.DataSets.GetDataSetByName('q1').GetValues()
q2_AttitudeVector = AttitudeVectorDPTimeVar.DataSets.GetDataSetByName('q2').GetValues()
q3_AttitudeVector = AttitudeVectorDPTimeVar.DataSets.GetDataSetByName('q3').GetValues()
q4_AttitudeVector = AttitudeVectorDPTimeVar.DataSets.GetDataSetByName('q4').GetValues()
wx_AttitudeVector = AttitudeVectorDPTimeVar.DataSets.GetDataSetByName('wx').GetValues()
wy_AttitudeVector = AttitudeVectorDPTimeVar.DataSets.GetDataSetByName('wy').GetValues()
wz_AttitudeVector = AttitudeVectorDPTimeVar.DataSets.GetDataSetByName('wz').GetValues()
wmag_AttitudeVector = AttitudeVectorDPTimeVar.DataSets.GetDataSetByName('w mag').GetValues()

##### Sun Vector (Inertial) #####

SunVectorDP = satellite.DataProviders.Item('Sun Vector')

SunVectorDP2 = SunVectorDP.QueryInterface(STKObjects.IAgDataProviderGroup)

SunVectorDP3 = SunVectorDP2.Group.Item('J2000')
#SunVectorDP3 = SunVectorDP2.Group.Item('ICRF')

SunVectorDP4 = SunVectorDP3.QueryInterface(STKObjects.IAgDataPrvTimeVar)

rptElements = ['Time','x','y','z']

SunVectorDPTimeVar = SunVectorDP4.ExecElements(scenario2.StartTime,
                                               scenario2.StopTime, time_step, rptElements)

x_SunVector_J2000 = SunVectorDPTimeVar.DataSets.GetDataSetByName('x').GetValues() #[km]
y_SunVector_J2000 = SunVectorDPTimeVar.DataSets.GetDataSetByName('y').GetValues() #[km]
z_SunVector_J2000 = SunVectorDPTimeVar.DataSets.GetDataSetByName('z').GetValues() #[km]

##### Sun Vector (Body - Fixed) #####

SunVectorDP = satellite.DataProviders.Item('Sun Vector')

SunVectorDP2 = SunVectorDP.QueryInterface(STKObjects.IAgDataProviderGroup)

SunVectorDP3 = SunVectorDP2.Group.Item('Fixed')

SunVectorDP4 = SunVectorDP3.QueryInterface(STKObjects.IAgDataPrvTimeVar)

rptElements = ['Time','x','y','z']

SunVectorDPTimeVar = SunVectorDP4.ExecElements(scenario2.StartTime,
                                               scenario2.StopTime, time_step, rptElements)

x_SunVector_Fixed = SunVectorDPTimeVar.DataSets.GetDataSetByName('x').GetValues() #[km]
y_SunVector_Fixed = SunVectorDPTimeVar.DataSets.GetDataSetByName('y').GetValues() #[km]
z_SunVector_Fixed = SunVectorDPTimeVar.DataSets.GetDataSetByName('z').GetValues() #[km]

##### Solar Intensity #####

SolarIntensityDP = satellite.DataProviders.Item('Solar Intensity')

SolarIntensityDP2 = SolarIntensityDP.QueryInterface(STKObjects.IAgDataPrvTimeVar)

rptElements = ['Time','Intensity','Percent Shadow','Current Condition',
               'Obstruction']

SolarIntensityDPTimeVar = SolarIntensityDP2.ExecElements(scenario2.StartTime,
                                                         scenario2.StopTime, time_step, rptElements)

Intensity_SolarIntensity = SolarIntensityDPTimeVar.DataSets.GetDataSetByName('Intensity').GetValues()
PercentShadow_SolarIntensity = SolarIntensityDPTimeVar.DataSets.GetDataSetByName('Percent Shadow').GetValues()
CurrentCondition_SolarIntensity = SolarIntensityDPTimeVar.DataSets.GetDataSetByName('Current Condition').GetValues()
Obstruction_SolarIntensity = SolarIntensityDPTimeVar.DataSets.GetDataSetByName('Obstruction').GetValues()

##### Mixed Shperical Elements [B1950] #####

SphericalElementsDP = satellite.DataProviders.Item('Mixed Spherical Elements')

SphericalElementsDP2 = SphericalElementsDP.QueryInterface(STKObjects.IAgDataProviderGroup)

SphericalElementsDP3 = SphericalElementsDP2.Group.Item('B1950')

SphericalElementsDP4 = SphericalElementsDP3.QueryInterface(STKObjects.IAgDataPrvTimeVar)

rptElements = ['Time','Detic Lat','Detic Lon','Detic Alt','Horiz Flt Path Ang',
               'Flt Path Azi','Velocity']

SphericalElementsDPTimeVar = SphericalElementsDP4.ExecElements(scenario2.StartTime,
                                                               scenario2.StopTime, time_step, rptElements)

DeticLat_SphericalElements = SphericalElementsDPTimeVar.DataSets.GetDataSetByName('Detic Lat').GetValues() #[degree]
DeticLon_SphericalElements = SphericalElementsDPTimeVar.DataSets.GetDataSetByName('Detic Lon').GetValues() #[degree]
DeticAlt_SphericalElements = SphericalElementsDPTimeVar.DataSets.GetDataSetByName('Detic Alt').GetValues() #[km]
HorizFltPathAng_SphericalElements = SphericalElementsDPTimeVar.DataSets.GetDataSetByName('Horiz Flt Path Ang').GetValues() #[degree]
FltPathAzi_SphericalElements = SphericalElementsDPTimeVar.DataSets.GetDataSetByName('Flt Path Azi').GetValues() #[degree]
Velocity_SphericalElements = SphericalElementsDPTimeVar.DataSets.GetDataSetByName('Velocity').GetValues() #[km/sec]

##### Vectors(Inertial) [MagField(IGRF)] #####

MagFieldDP = target.DataProviders.Item('Vectors(J2000)')

MagFieldDP2 = MagFieldDP.QueryInterface(STKObjects.IAgDataProviderGroup)

MagFieldDP3 = MagFieldDP2.Group.Item('MagField(IGRF)')

MagFieldDP4 = MagFieldDP3.QueryInterface(STKObjects.IAgDataPrvTimeVar)

rptElements = ['Time','x','y','z','Magnitude','x/Magnitude','y/Magnitude',
               'z/Magnitude','RightAscension','Declination','Co-Declination',
               'NegativeDeclination','DirectionAngle x','DirectionAngle y',
               'DirectionAngle z','Derivative x','Derivative y','Derivative z',
               'Derivative Magnitude']

MagFieldDPTimeVar = MagFieldDP4.ExecElements(scenario2.StartTime,scenario2.StopTime, time_step, rptElements)

x_MagField_J2000 = MagFieldDPTimeVar.DataSets.GetDataSetByName('x').GetValues() #[nT]
y_MagField_J2000 = MagFieldDPTimeVar.DataSets.GetDataSetByName('y').GetValues() #[nT]
z_MagField_J2000 = MagFieldDPTimeVar.DataSets.GetDataSetByName('z').GetValues() #[nT]
Magnitude_MagField_J2000 = MagFieldDPTimeVar.DataSets.GetDataSetByName('Magnitude').GetValues() #[nT]
xMagnitude_MagField_J2000 = MagFieldDPTimeVar.DataSets.GetDataSetByName('x/Magnitude').GetValues() 
yMagnitude_MagField_J2000 = MagFieldDPTimeVar.DataSets.GetDataSetByName('y/Magnitude').GetValues() 
zMagnitude_MagField_J2000 = MagFieldDPTimeVar.DataSets.GetDataSetByName('z/Magnitude').GetValues() 

##### Vectors(Body - Fixed) [MagField(IGRF)] #####

MagFieldDP = satellite.DataProviders.Item('Vectors(Fixed)')

MagFieldDP2 = MagFieldDP.QueryInterface(STKObjects.IAgDataProviderGroup)

MagFieldDP3 = MagFieldDP2.Group.Item('MagField(IGRF)')

MagFieldDP4 = MagFieldDP3.QueryInterface(STKObjects.IAgDataPrvTimeVar)

rptElements = ['Time','x','y','z','Magnitude','x/Magnitude','y/Magnitude',
               'z/Magnitude','RightAscension','Declination','Co-Declination',
               'NegativeDeclination','DirectionAngle x','DirectionAngle y',
               'DirectionAngle z','Derivative x','Derivative y','Derivative z',
               'Derivative Magnitude']

MagFieldDPTimeVar = MagFieldDP4.ExecElements(scenario2.StartTime,scenario2.StopTime, time_step, rptElements)

x_MagField_Fixed = MagFieldDPTimeVar.DataSets.GetDataSetByName('x').GetValues() #[nT]
y_MagField_Fixed = MagFieldDPTimeVar.DataSets.GetDataSetByName('y').GetValues() #[nT]
z_MagField_Fixed = MagFieldDPTimeVar.DataSets.GetDataSetByName('z').GetValues() #[nT]
Magnitude_MagField_Fixed = MagFieldDPTimeVar.DataSets.GetDataSetByName('Magnitude').GetValues() #[nT]
xMagnitude_MagField_Fixed = MagFieldDPTimeVar.DataSets.GetDataSetByName('x/Magnitude').GetValues() 
yMagnitude_MagField_Fixed = MagFieldDPTimeVar.DataSets.GetDataSetByName('y/Magnitude').GetValues() 
zMagnitude_MagField_Fixed = MagFieldDPTimeVar.DataSets.GetDataSetByName('z/Magnitude').GetValues() 

##### Vectors(Inertial) [Position(Sun)] #####

SunPositionDP = satellite.DataProviders.Item('Vectors(J2000)')

SunPositionDP2 = SunPositionDP.QueryInterface(STKObjects.IAgDataProviderGroup)

SunPositionDP3 = SunPositionDP2.Group.Item('Position(Sun)')

SunPositionDP4 = SunPositionDP3.QueryInterface(STKObjects.IAgDataPrvTimeVar)

rptElements = ['Time','x','y','z','Magnitude','x/Magnitude','y/Magnitude',
               'z/Magnitude','RightAscension','Declination','Co-Declination',
               'NegativeDeclination','DirectionAngle x','DirectionAngle y',
               'DirectionAngle z','Derivative x','Derivative y','Derivative z',
               'Derivative Magnitude']

SunPositionDPTimeVar = SunPositionDP4.ExecElements(scenario2.StartTime,scenario2.StopTime, time_step, rptElements)

x_SunPosition_J2000 = SunPositionDPTimeVar.DataSets.GetDataSetByName('x').GetValues() #[km]
y_SunPosition_J2000 = SunPositionDPTimeVar.DataSets.GetDataSetByName('y').GetValues() #[km]
z_SunPosition_J2000 = SunPositionDPTimeVar.DataSets.GetDataSetByName('z').GetValues() #[km]
Magnitude_SunPosition_J2000 = SunPositionDPTimeVar.DataSets.GetDataSetByName('Magnitude').GetValues() #[km]
xMagnitude_SunPosition_J2000 = SunPositionDPTimeVar.DataSets.GetDataSetByName('x/Magnitude').GetValues() 
yMagnitude_SunPosition_J2000 = SunPositionDPTimeVar.DataSets.GetDataSetByName('y/Magnitude').GetValues() 
zMagnitude_SunPosition_J2000 = SunPositionDPTimeVar.DataSets.GetDataSetByName('z/Magnitude').GetValues() 

##### Vectors(Inertial) [Sunlight] #####

SunlightDP = satellite.DataProviders.Item('Vectors(J2000)')

SunlightDP2 = SunlightDP.QueryInterface(STKObjects.IAgDataProviderGroup)

SunlightDP3 = SunlightDP2.Group.Item('Sunlight')

SunlightDP4 = SunlightDP3.QueryInterface(STKObjects.IAgDataPrvTimeVar)

rptElements = ['Time','x','y','z','Magnitude','x/Magnitude','y/Magnitude',
               'z/Magnitude','RightAscension','Declination','Co-Declination',
               'NegativeDeclination','DirectionAngle x','DirectionAngle y',
               'DirectionAngle z','Derivative x','Derivative y','Derivative z',
               'Derivative Magnitude']

SunlightDPTimeVar = SunlightDP4.ExecElements(scenario2.StartTime,scenario2.StopTime,
                                             time_step, rptElements)

x_Sunlight_J2000 = SunlightDPTimeVar.DataSets.GetDataSetByName('x').GetValues() #[km]
y_Sunlight_J2000 = SunlightDPTimeVar.DataSets.GetDataSetByName('y').GetValues() #[km]
z_Sunlight_J2000 = SunlightDPTimeVar.DataSets.GetDataSetByName('z').GetValues() #[km]
Magnitude_Sunlight_J2000 = SunlightDPTimeVar.DataSets.GetDataSetByName('Magnitude').GetValues() #[km]
xMagnitude_Sunlight_J2000 = SunlightDPTimeVar.DataSets.GetDataSetByName('x/Magnitude').GetValues() 
yMagnitude_Sunlight_J2000 = SunlightDPTimeVar.DataSets.GetDataSetByName('y/Magnitude').GetValues() 
zMagnitude_Sunlight_J2000 = SunlightDPTimeVar.DataSets.GetDataSetByName('z/Magnitude').GetValues()

##### Body Axes Orientation #####

J2000DP = satellite.DataProviders.Item('Body Axes Orientation')

J2000DP2 = J2000DP.QueryInterface(STKObjects.IAgDataProviderGroup)

J2000DP3 = J2000DP2.Group.Item('J2000') #<--------Usando ICRF para o q_IS
LVLHDP3 = J2000DP2.Group.Item('LVLH') #<--------Usando LVLH para o q_CS
VNCDP3 = J2000DP2.Group.Item('VNC')   #<--------Usando VNC para o q_OS

J2000DP4 = J2000DP3.QueryInterface(STKObjects.IAgDataPrvTimeVar)
LVLHDP4 = LVLHDP3.QueryInterface(STKObjects.IAgDataPrvTimeVar)
VNCDP4 = VNCDP3.QueryInterface(STKObjects.IAgDataPrvTimeVar)

rptElements = ['Time','YPR321 yaw','YPR321 pitch','YPR321 roll','Euler321 precession',
               'Euler321 nutation','Euler321 spin','Euler323 precession',
               'Euler323 nutation','Euler323 spin','q1','q2','q3','q4',
               'wx','wy','wz','w mag','RightAscension of w','Declination of w',
               'Eigen-Angle','Eigen-Axis x','Eigen-Axis y','Eigen-Axis z']

J2000DPTimeVar = J2000DP4.ExecElements(scenario2.StartTime,scenario2.StopTime, 
                                     time_step, rptElements)
LVLHDPTimeVar = LVLHDP4.ExecElements(scenario2.StartTime,scenario2.StopTime, 
                                     time_step, rptElements)
VNCDPTimeVar = VNCDP4.ExecElements(scenario2.StartTime,scenario2.StopTime, 
                                     time_step, rptElements)

q1_J2000 = J2000DPTimeVar.DataSets.GetDataSetByName('q1').GetValues()
q2_J2000 = J2000DPTimeVar.DataSets.GetDataSetByName('q2').GetValues()
q3_J2000 = J2000DPTimeVar.DataSets.GetDataSetByName('q3').GetValues()
q4_J2000 = J2000DPTimeVar.DataSets.GetDataSetByName('q4').GetValues()
wx_J2000 = J2000DPTimeVar.DataSets.GetDataSetByName('wx').GetValues()
wy_J2000 = J2000DPTimeVar.DataSets.GetDataSetByName('wy').GetValues()
wz_J2000 = J2000DPTimeVar.DataSets.GetDataSetByName('wz').GetValues()

q1_LVLH = LVLHDPTimeVar.DataSets.GetDataSetByName('q1').GetValues()
q2_LVLH = LVLHDPTimeVar.DataSets.GetDataSetByName('q2').GetValues()
q3_LVLH = LVLHDPTimeVar.DataSets.GetDataSetByName('q3').GetValues()
q4_LVLH = LVLHDPTimeVar.DataSets.GetDataSetByName('q4').GetValues()
wx_LVLH = LVLHDPTimeVar.DataSets.GetDataSetByName('wx').GetValues()
wy_LVLH = LVLHDPTimeVar.DataSets.GetDataSetByName('wy').GetValues()
wz_LVLH = LVLHDPTimeVar.DataSets.GetDataSetByName('wz').GetValues()

q1_VNC = VNCDPTimeVar.DataSets.GetDataSetByName('q1').GetValues()
q2_VNC = VNCDPTimeVar.DataSets.GetDataSetByName('q2').GetValues()
q3_VNC = VNCDPTimeVar.DataSets.GetDataSetByName('q3').GetValues()
q4_VNC = VNCDPTimeVar.DataSets.GetDataSetByName('q4').GetValues()
wx_VNC = VNCDPTimeVar.DataSets.GetDataSetByName('wx').GetValues()
wy_VNC = VNCDPTimeVar.DataSets.GetDataSetByName('wy').GetValues()
wz_VNC = VNCDPTimeVar.DataSets.GetDataSetByName('wz').GetValues()

########################### QUIT STK APPLICATION ##############################

uiApplication.Quit()

################################################################################

## APPLICATION EXECUTION TIMER STARTER
start_time = time.time()

## ROTATION MATRIX FROM INERTIAL REFERENCE FRAME TO ORBITAL REFERENCE FRAME
R_OI = np.matmul(rotmZ(math.radians(ArgOfPerigee_J2000[0])),
                 np.matmul(rotmX(math.radians(Inclination_J2000[0])),
                           rotmZ(math.radians(RAAN_J2000[0]))))

# THE SCALAR ELEMENT IS THE FIRST ELEMENT OF THE QUATERNION
q_OI = quaternion_continuity(R_OI)

## INVERSE MATRIX TO OBTAIN ROTATION MATRIX FROM ORBITAL REFERENCE FRAME TO INERTIAL REFERENCE FRAME
R_IO = np.transpose(R_OI)

# THE SCALAR ELEMENT IS THE FIRST ELEMENT OF THE QUATERNION
q_IO = quaternion_continuity(R_IO)

###############################################################################
## ROTATION MATRIX FROM CONTROLL REFERENCE FRAME TO BODY REFERENCE FRAME
R_SC = np.eye(3)

# THE SCALAR ELEMENT IS THE FIRST ELEMENT OF THE QUATERNION
q_SC = quaternion_continuity(R_SC)

## INVERSE MATRIX TO OBTAIN ROTATION MATRIX FROM BODY REFERENCE FRAME TO CONTROLL REFERENCE FRAME
R_CS = np.linalg.inv(R_SC)

# THE SCALAR ELEMENT IS THE FIRST ELEMENT OF THE QUATERNION
q_CS = quaternion_continuity(R_CS)

###############################################################################
# THE SCALAR ELEMENT IS THE FIRST ELEMENT OF THE QUATERNION
q_IS = Quaternion(vector=[q1_J2000[0],q2_J2000[0],q3_J2000[0]],scalar=q4_J2000[0])

## INVERSE MATRIX TO OBTAIN ROTATION MATRIX FROM BODY REFERENCE FRAME TO INERTIAL REFERENCE FRAME
R_IS = q_IS.rotation_matrix

## ROTATION MATRIX FROM INNERTIAL REFERENCE FRAME TO BODY REFERENCE FRAME
R_SI = np.transpose(R_IS)

# THE SCALAR ELEMENT IS THE FIRST ELEMENT OF THE QUATERNION
q_SI = quaternion_continuity(R_SI)

###############################################################################
## ROTATION MATRIX FROM INERTIAL REFERENCE FRAME TO CONTROLLER REFERENCE FRAME
R_CI = np.matmul(R_CS,R_SI)

# THE SCALAR ELEMENT IS THE FIRST ELEMENT OF THE QUATERNION
q_CI = quaternion_continuity(R_CI)

## ROTATION MATRIX FROM CONTROLL REFERENCE FRAME TO INERTIAL REFERENCE FRAME
R_IC = np.transpose(R_CI)

# THE SCALAR ELEMENT IS THE FIRST ELEMENT OF THE QUATERNION
q_IC = quaternion_continuity(R_IC)

###############################################################################
######## VELOCITY/POSITION VECTOR - INERTIAL/ORBITAL REFERENCE FRAME ##########
###############################################################################

## INFORMATION OBTAINED WITH STK

#[km]
rI_0 = np.matrix([x_Position[0],y_Position[0],z_Position[0]])
rO_0 = np.matmul(R_OI,np.transpose(rI_0))

#[km/seconds]
vI_0 = np.matrix([xVelocity_ICRF[0],yVelocity_ICRF[0],zVelocity_ICRF[0]])
vO_0 = np.matmul(R_OI,np.transpose(vI_0))

###############################################################################
###################### GENERAL DATA ABOUT THE SATELLITE #######################
###############################################################################

## SATELITTE ALTITUDE
altitude = 778 #[km]

## TOTAL MASS OF THE SATELLITE
mass_satellite = 2080 #[kg]

## SECOND MOMENT OF INERTIA OF THE SATELLITE FROM STK

#dim_x = 1.8 #[m]
#dim_y = 2.0 #[m]
#dim_z = 2.5 #[m]
#
#Ixx = (1/12)*mass_satellite*((dim_y**2)+(dim_x**2))
#Iyy = (1/12)*mass_satellite*((dim_z**2)+(dim_x**2))
#Izz = (1/12)*mass_satellite*((dim_z**2)+(dim_y**2))

## CONSIDERS A CUBE PERFECTLY SYMMETRIC, WITH SOLAR PANEL CLOSED

Ixx = 4500 #[kg*m2]
Iyy = 4500 #[kg*m2]
Izz = 4500 #[kg*m2]

I_satellite = np.matrix([[Ixx,0,0],[0,Iyy,0],[0,0,Izz]])

###############################################################################
################# ANGULAR VELOCITY - INERTIAL REFERENCE FRAME #################
###############################################################################

## NOISE ADDED TO SENSORS MEASUREMENTS

noise_omega = 5.5704e-4
noise_vsun = (10/3)/360
noise_vmag = 3/360

## INITIAL ANGULAR VELOCITY ON INERTIAL REFERENCE FRAME
omega_I_0 = np.array([wx_J2000[0],wy_J2000[0],wz_J2000[0]]) #[radians/seconds]
omega_S_0 = np.matmul(R_SI,omega_I_0)

## SKEW MATRIX
skew_omega_I_0 = skew(omega_I_0)

Omega_I_0 = Omega(omega_I_0)

Ac1 = ((1/2)*(Omega_I_0))
Ac1 = np.c_[Ac1,np.zeros((4,3))]
Ac2 = np.zeros((3,4))
Ac2 = np.c_[Ac2,np.matmul((-np.linalg.inv(I_satellite)),np.matmul(skew_omega_I_0,I_satellite))]
Ac = np.zeros((7,7))
Ac = np.r_[Ac1,Ac2]

omega_I_k_kminus = np.array([wx_J2000[0],wy_J2000[0],wz_J2000[0]]) #[radians/seconds]
omega_S_k = np.matmul(R_SI,omega_I_k_kminus) #[radians/seconds]
omega_S_k = [omega_S_k[0] * (1+(random.uniform(0.0,1.0)-0.5)*noise_omega), omega_S_k[1] * (1+(random.uniform(0.0,1.0)-0.5)*noise_omega), omega_S_k[2] * (1+(random.uniform(0.0,1.0)-0.5)*noise_omega)]

###############################################################################
############################ SUN POSITION INITIAL #############################
###############################################################################

vsun_I_k_kminus = np.matrix([x_SunVector_J2000[0],y_SunVector_J2000[0],z_SunVector_J2000[0]])
vsun_S_k = np.matmul(R_SI,np.transpose(vsun_I_k_kminus))
vsun_S_k = np.transpose(vsun_S_k)
vsun_S_k = np.matrix([(vsun_S_k[0,0] * (1+(random.uniform(0.0,1.0)-0.5)*noise_vsun)), (vsun_S_k[0,1] * (1+(random.uniform(0.0,1.0)-0.5)*noise_vsun)), (vsun_S_k[0,2] * (1+(random.uniform(0.0,1.0)-0.5)*noise_vsun))])

vsun_I_k_kminus_unit = (np.transpose(vsun_I_k_kminus[:])/np.linalg.norm(vsun_I_k_kminus[:]))
vsun_S_k_unit = (np.transpose(vsun_S_k[:])/np.linalg.norm(vsun_S_k[:]))

###############################################################################
########################## MAGNETIC FIELD INITIAL #############################
###############################################################################

vmag_I_k_kminus = np.matrix([x_MagField_J2000[0],y_MagField_J2000[0],z_MagField_J2000[0]])
vmag_S_k = np.matmul(R_SI,np.transpose(vmag_I_k_kminus))
vmag_S_k = np.transpose(vmag_S_k)
vmag_S_k = np.matrix([(vmag_S_k[0,0] * (1+(random.uniform(0.0,1.0)-0.5)*noise_vmag), vmag_S_k[0,1] * (1+(random.uniform(0.0,1.0)-0.5)*noise_vmag), vmag_S_k[0,2] * (1+(random.uniform(0.0,1.0)-0.5)*noise_vmag))])

vmag_I_k_kminus_unit = (np.transpose(vmag_I_k_kminus[:])/np.linalg.norm(vmag_I_k_kminus[:]))
vmag_S_k_unit = (np.transpose(vmag_S_k[:])/np.linalg.norm(vmag_S_k[:]))

###############################################################################
##################### CONSTANTS FOR UKF IMPLEMENTATION ########################
###############################################################################

## NON-NEGATIVE WEIGHTS - INVERSE VARIANCE OF THE MEASUREMENT NOISE

sigma_sun = 0.0034        # INVERSE VARIANCE OF THE MEASUREMENT NOISE OF THE SOLAR SENSOR (a1)
sigma_mag = 0.0027        # INVERSE VARIANCE OF THE MEASUREMENT NOISE OF THE MAGNETOMETER SENSOR (a2)
sigma_omega = 0.000012     # INVERSE VARIANCE OF THE MEASUREMENT NOISE OF THE ANGULAR VELOCITY

#PROCESS NOISE MATRIX Q

Q = np.matrix([
      [1,0,0,0,0,0],
      [0,1,0,0,0,0],
      [0,0,1,0,0,0],
      [0,0,0,10,0,0],
      [0,0,0,0,10,0],
      [0,0,0,0,0,10]
      ])

Q = Q*(10**-6)                 

#MEASUREMENT NOISE MATRIX R

R = np.matrix([
        [3.4,0,0,0,0,0,0,0,0],
        [0,3.4,0,0,0,0,0,0,0],
        [0,0,3.4,0,0,0,0,0,0],
        [0,0,0,2.7,0,0,0,0,0],
        [0,0,0,0,2.7,0,0,0,0],
        [0,0,0,0,0,2.7,0,0,0],
        [0,0,0,0,0,0,0.012,0,0],
        [0,0,0,0,0,0,0,0.012,0],
        [0,0,0,0,0,0,0,0,0.012]
        ])

R = R*(10**-2)

#INITIAL ERROR COVARIANCE MATRIX

P0 = np.matrix([
      [1,0,0,0,0,0],
      [0,1,0,0,0,0],
      [0,0,1,0,0,0],
      [0,0,0,1,0,0],
      [0,0,0,0,1,0],
      [0,0,0,0,0,1]
      ])

P0 = P0*(10**-3)

P_kminus_kminus = P0    #FOR THE FIRST STEP

###############################################################################
############################## INITIALIZATION #################################
###############################################################################

## 0.1 SOLVE WAHBA (SVD):

B = (sigma_sun) * np.matmul(vsun_S_k_unit, np.transpose(vsun_I_k_kminus_unit)) + (sigma_mag) * np.matmul(vmag_S_k_unit, np.transpose(vmag_I_k_kminus_unit))

U,S,V = np.linalg.svd(B)

A_SI_opt_aux = np.matrix([
                          [1,0,0],
                          [0,1,0],
                          [0,0,(np.linalg.det(U)*np.linalg.det(V))]
                          ])

A_SI_opt = np.matmul(U, np.matmul(A_SI_opt_aux, V))

## 0.2 CALCULATE q0_SI:

q0_SI = quaternion_continuity(A_SI_opt)

## 0.3 INITIALIZE STATE:

aux1 = quaternion_multiply(q0_SI,q_CS)
x_k_k = np.c_[np.matrix([aux1[0], aux1[1], aux1[2], aux1[3]]), np.matrix([q_CS.rotate(omega_S_0)])]

## 0.4 CALCULATE WEIGHTS:

#Normally has a small positive value between (10e-4) <= alpha <= 1 and it determines the
#spread of the sigma points
alpha = np.sqrt(3)

#Scaling parameter incorporates prior knowledge of the distribution of the state vector.
beta = 2.0

L = np.shape(x_k_k)
L = np.subtract(L, (0,1))

#Secundary factor scaling defined as 0 or 3-n.
kappa = 0.0

lmbd = (alpha**(2))*kappa - (1-(alpha**(2)))*float(L[1])

W_m = np.zeros((1,2*int(L[1])+1))
W_c = np.zeros((1,2*int(L[1])+1))
W_m[0][0] = lmbd/(float(L[1])+lmbd)
W_c[0][0] = (lmbd/(float(L[1])+lmbd)) + 1 - (alpha**(2)) + beta

for i in range(1,2*int(L[1])+1):
    
    W_m[0][i] = 1/(2*(float(L[1])+lmbd))
    W_c[0][i] = 1/(2*(float(L[1])+lmbd))

## 0.5 SAVE:

R_CI_k_k = q0_SI.rotation_matrix
q_CI_k_k = quaternion_continuity(R_CI_k_k)

q_CI_kminus_kminus = q_CI_k_k
q_CI_k_kminus = q_CI_k_k

omega_C_k_kminus = np.matmul(R_CS,omega_S_k)
omega_C_kminus_kminus = omega_C_k_kminus

vsun_S_k_save = np.zeros((1,3))
vmag_S_k_save = np.zeros((1,3))
omega_S_k_save = np.zeros((1,3))

vsun_S_k_save[0][:] = vsun_S_k
vmag_S_k_save[0][:] = vmag_S_k
omega_S_k_save[0][:] = omega_S_k

#N_ctrl_save = np.zeros((1,3))

Output = np.zeros((6,1))

P_sum_save = np.zeros((1,1))

P_sum_save[0][:] = P_kminus_kminus.item(0,0)+P_kminus_kminus.item(0,1)+P_kminus_kminus.item(0,2) + P_kminus_kminus.item(1,0)+P_kminus_kminus.item(1,1)+P_kminus_kminus.item(1,2) + P_kminus_kminus.item(2,0)+P_kminus_kminus.item(2,1)+P_kminus_kminus.item(2,2)

for j in range(1,len(timer)):
    ###############################################################################
    ################################## PREDICT ####################################
    ###############################################################################
    
    ## 1.1 ERROR SIGMA POINTS:
    print('Iteration ' + str(j) + ': 1.1 ERROR SIGMA POINTS')
    aux1 = np.zeros((6,1))
    R_aux = (float(L[1])+lmbd)*P_kminus_kminus
    R_aux = ValidateCovarianceMatrix(R_aux)

    if len(R_aux) == 1:
        print('Error covariance matrix...')
    delchi_kminus_kminus = np.matrix(aux1)
    delchi_kminus_kminus = np.c_[delchi_kminus_kminus,-np.transpose(scipy.linalg.cholesky(R_aux,lower=False,overwrite_a=True))]
    delchi_kminus_kminus = np.c_[delchi_kminus_kminus,np.transpose(scipy.linalg.cholesky(R_aux,lower=False,overwrite_a=True))]
    
    ## 1.2 FULL SIGMA POINTS:
    print('Iteration ' + str(j) + ': 1.2 FULL SIGMA POINTS')
    Chi_kminus_kminus = np.zeros((int(L[1]+1),2*int(L[1])+1))
    
    for k in range(0,2*int(L[1])+1):

        aux1 = np.transpose(delchi_kminus_kminus[[0,1,2],:][:,[k]])
        
        aux1 = np.c_[aux1,math.sqrt(math.fabs(1-np.matmul(np.transpose(delchi_kminus_kminus[[0,1,2],:][:,[k]]),delchi_kminus_kminus[[0,1,2],:][:,[k]])))]
        aux1 = Quaternion(vector=[aux1[0][:,[0]],aux1[0][:,[1]],aux1[0][:,[2]]],scalar=aux1[0][:,[3]])
        aux1 = aux1*q_CI_kminus_kminus
        aux1 = np.transpose(np.matrix([aux1[0],aux1[1],aux1[2],aux1[3]]))
        aux2 = np.transpose(omega_I_k_kminus + np.transpose(delchi_kminus_kminus[[3,4,5],:][:,[k]]))
        aux3 = np.r_[aux1,aux2]
        Chi_kminus_kminus[:,:][:,[k]] = aux3

    ## 1.3 ROTATE CONTROL TORQUE:
    print('Iteration ' + str(j) + ': 1.3 ROTATE CONTROL TORQUE')
    N_ctrl_kminus = np.zeros((3,1))
    
    N_ctrl_kminus = np.matrix([q_CS.rotate(N_ctrl_kminus)])

    ## 1.4 NUMERICAL PROPAGATION:
    print('Iteration ' + str(j) + ': 1.4 NUMERICAL PROPAGATION')
    Chi_k_kminus = []
    
    for l in range(0,int(np.shape(Chi_kminus_kminus)[1])):
        chi = np.transpose(Chi_kminus_kminus[:,:][:,[l]])
        chi = np.array([chi[0][0],chi[0][1],chi[0][2],chi[0][3],chi[0][4],chi[0][5],chi[0][6]])
        y =  np.array([chi[0],chi[1],chi[2],chi[3]])
        w = np.array([chi[4],chi[5],chi[6]])
        t = [0, time_step]
        t_eval = np.linspace(0, time_step, time_step**2)
        args = (w, I_satellite, N_ctrl_kminus)
        
        Chi = solve_ivp(lambda t, y: Equations(t,y,*args), [0, time_step], y, method='RK45', rtol=10**(-3),atol=10**(-6))
        data = [x[int(np.shape(Chi.y)[1]-1)] for x in Chi.y]
        data = [data[0],data[1],data[2],data[3],chi[4],chi[5],chi[6]]
        if l == 0:
            Chi_k_kminus = np.r_[Chi_k_kminus,data]
        else:
            Chi_k_kminus = np.c_[Chi_k_kminus,data]
            

    ## 1.5 A PRIORI STATE ESTIMATE:
    print('Iteration ' + str(j) + ': 1.5 A PRIORI STATE ESTIMATE')
    for n in range(0,2*int(L[1])+1):
        if n == 0:
            x_hat_minus1 = np.array([W_m[0,n]])*np.array([Chi_k_kminus[0][n],Chi_k_kminus[1][n],Chi_k_kminus[2][n],Chi_k_kminus[3][n]])
            x_hat_minus2 = np.array([W_m[0,n]])*np.array([Chi_k_kminus[4][n],Chi_k_kminus[5][n],Chi_k_kminus[6][n]])
        else:
            x_hat_minus1 = x_hat_minus1 + np.array([W_m[0,n]])*np.array([Chi_k_kminus[0][n],Chi_k_kminus[1][n],Chi_k_kminus[2][n],Chi_k_kminus[3][n]])
            x_hat_minus2 = x_hat_minus2 + np.array([W_m[0,n]])*np.array([Chi_k_kminus[4][n],Chi_k_kminus[5][n],Chi_k_kminus[6][n]])
    
    x_hat_minus1 = x_hat_minus1/np.linalg.norm(x_hat_minus1)
    x_k_kminus = np.c_[np.reshape(x_hat_minus1,(1,4)),np.reshape(x_hat_minus2,(1,3))]
    
    ## 1.6 FULL TO ERROR STATE:
    print('Iteration ' + str(j) + ': 1.6 FULL TO ERROR STATE')
    delChi_k_kminus = []
    
    for m in range(0,2*int(L[1])+1):
        q_aux = Quaternion(vector=x_k_kminus[0][1:4],scalar=x_k_kminus[0][0:1])
        ChiQ1 = quaternion_multiply(Quaternion(vector=Chi_k_kminus[:,m][1:4],scalar=Chi_k_kminus[:,m][0:1]),quaternion_inverse(q_aux))
        ChiQ2 = np.array([Chi_k_kminus[4][m],Chi_k_kminus[5][m],Chi_k_kminus[6][m]])-(x_k_kminus[0][4:7])
        data = np.array([ChiQ1[1],ChiQ1[2],ChiQ1[3],ChiQ2[0],ChiQ2[1],ChiQ2[2]])
        if m == 0:
            delChi_k_kminus = np.r_[delChi_k_kminus,data]
        else:
            delChi_k_kminus = np.c_[delChi_k_kminus,data]
    
    ## 1.7 MEAN ERROR STATE:
    print('Iteration ' + str(j) + ': 1.7 MEAN ERROR STATE')
    for o in range(0,2*int(L[1])+1):
        if o == 0:
            delx_k_kminus = np.array([W_m[0,o]])*np.array([delChi_k_kminus[0][o],delChi_k_kminus[1][o],delChi_k_kminus[2][o],delChi_k_kminus[3][o],delChi_k_kminus[4][o],delChi_k_kminus[5][o]])
        else:
            delx_k_kminus = delx_k_kminus + np.array([W_m[0,o]])*np.array([delChi_k_kminus[0][o],delChi_k_kminus[1][o],delChi_k_kminus[2][o],delChi_k_kminus[3][o],delChi_k_kminus[4][o],delChi_k_kminus[5][o]])
    
    ## 1.8 A PRIORI COVARIANCE:
    print('Iteration ' + str(j) + ': 1.8 A PRIORI COVARIANCE')
    for p in range(0,2*int(L[1])+1):
        if p ==0:
            P_k_kminus = np.array([W_c[0,p]])*np.matmul(np.reshape((np.array([delChi_k_kminus[0][p],delChi_k_kminus[1][p],delChi_k_kminus[2][p],delChi_k_kminus[3][p],delChi_k_kminus[4][p],delChi_k_kminus[5][p]]) - delx_k_kminus),(6,1)),np.reshape((np.array([delChi_k_kminus[0][p],delChi_k_kminus[1][p],delChi_k_kminus[2][p],delChi_k_kminus[3][p],delChi_k_kminus[4][p],delChi_k_kminus[5][p]]) - delx_k_kminus),(1,6)))
        else:
            P_k_kminus = P_k_kminus + np.array([W_c[0,p]])*np.matmul(np.reshape((np.array([delChi_k_kminus[0][p],delChi_k_kminus[1][p],delChi_k_kminus[2][p],delChi_k_kminus[3][p],delChi_k_kminus[4][p],delChi_k_kminus[5][p]]) - delx_k_kminus),(6,1)),np.reshape((np.array([delChi_k_kminus[0][p],delChi_k_kminus[1][p],delChi_k_kminus[2][p],delChi_k_kminus[3][p],delChi_k_kminus[4][p],delChi_k_kminus[5][p]]) - delx_k_kminus),(1,6)))
    
    P_k_kminus = P_k_kminus + Q
    
    ###############################################################################
    ################################### UPDATE ####################################
    ###############################################################################
    ###############################################################################

    # THE SCALAR ELEMENT IS THE FIRST ELEMENT OF THE QUATERNION
    q_IS_aux1 = Quaternion(vector=[q1_J2000[j-1],q2_J2000[j-1],q3_J2000[j-1]],scalar=q4_J2000[j-1])
    q_IS_aux2 = Quaternion(vector=[q1_J2000[j],q2_J2000[j],q3_J2000[j]],scalar=q4_J2000[j])
    q_IS = quaternion_antipod(q_IS_aux1,q_IS_aux2)
    
    ## INVERSE MATRIX TO OBTAIN ROTATION MATRIX FROM BODY REFERENCE FRAME TO INERTIAL REFERENCE FRAME
    R_IS = q_IS.rotation_matrix
    
    # THE SCALAR ELEMENT IS THE FIRST ELEMENT OF THE QUATERNION
    q_SI = q_IS.inverse

    ## ROTATION MATRIX FROM INNERTIAL REFERENCE FRAME TO BODY REFERENCE FRAME
    R_SI = q_SI.rotation_matrix

    # THE SCALAR ELEMENT IS THE FIRST ELEMENT OF THE QUATERNION
#    q_CS = Quaternion(matrix=R_CS)
    q_CS = quaternion_continuity(R_CS)
    q_CI = q_CS*q_SI
    
    ## ROTATION MATRIX FROM INERTIAL REFERENCE FRAME TO CONTROLLER REFERENCE FRAME
    R_CI = np.matmul(R_CS,R_SI)
    
    ## 2.1 SAVE:
    print('Iteration ' + str(j) + ': 2.1 SAVE')

    ########################## ANGULAR VELOCITY UPDATE ############################
    
    omega_I_k_kminus = np.matrix([wx_J2000[j-1],wy_J2000[j-1],wz_J2000[j-1]]) #[radians/seconds]
    omega_S_k = np.transpose(np.matmul(np.matmul(R_SC,R_CI),np.transpose(omega_I_k_kminus))) #[radians/seconds]
    omega_S_k = [omega_S_k[0,0] +(random.uniform(-1.0,1.0)*noise_omega), omega_S_k[0,1] +(random.uniform(-1.0,1.0)*noise_omega), omega_S_k[0,2] +(random.uniform(-1.0,1.0)*noise_omega)]

    ############################ SUN POSITION UPDATE ##############################
    
    vsun_I_k_kminus = np.matrix([x_SunVector_J2000[j-1],y_SunVector_J2000[j-1],z_SunVector_J2000[j-1]])
    vsun_S_k = np.transpose(np.matmul(R_SI,np.transpose(vsun_I_k_kminus)))  
    vsun_S_k = [vsun_S_k[0,0] * (1+(random.uniform(-1.0,1.0)*noise_vsun)), vsun_S_k[0,1] * (1+(random.uniform(-1.0,1.0)*noise_vsun)), vsun_S_k[0,2] * (1+(random.uniform(-1.0,1.0)*noise_vsun))]
    
    ########################## MAGNETIC FIELD UPDATE ##############################

    vmag_I_k_kminus = np.matrix([x_MagField_J2000[j-1],y_MagField_J2000[j-1],z_MagField_J2000[j-1]])
    vmag_S_k = np.transpose(np.matmul(R_SI,np.transpose(vmag_I_k_kminus)))
    vmag_S_k = [vmag_S_k[0,0] * (1+(random.uniform(-1.0,1.0)*noise_vmag)), vmag_S_k[0,1] * (1+(random.uniform(-1.0,1.0)*noise_vmag)), vmag_S_k[0,2] * (1+(random.uniform(-1.0,1.0)*noise_vmag))]
        
    vsun_S_k_save = np.r_[vsun_S_k_save,[vsun_S_k]]
    vmag_S_k_save = np.r_[vmag_S_k_save,[vmag_S_k]]
    omega_S_k_save = np.r_[omega_S_k_save,[omega_S_k]]
    
    ## 2.2 ECLIPSE CHECK:
    print('Iteration ' + str(j) + ': 2.2 ECLIPSE CHECK')
    if x_Sunlight_J2000[j] == 0.0 or y_Sunlight_J2000[j] == 0.0 or z_Sunlight_J2000[j] == 0.0:
        r = 0
        ## 2.6 HARDCODE VECTOR:
        print('Iteration ' + str(j) + ': 2.6 HARDCODE VECTOR')
        eclipse = 1
    else:
        r = 1
        eclipse = 0
    
    ## 2.7 REPEAT STEP 2.3 TO 2.6:
    
    while r < 4:
        
        if r == 1:
            ## 2.3 NEW MEASUREMENT?:
            print('Iteration ' + str(j) + ': 2.3 NEW MEASUREMENT?')
            comparison = vsun_S_k_save[j-1] == vsun_S_k_save[j]
            equal_arrays = comparison.all()
            
            if equal_arrays == False:
                
                ## 2.4 NORMALIZE AND ROTATE:
                print('Iteration ' + str(j) + ': 2.4 NORMALIZE AND ROTATE')
                vsun_C_k = np.matmul((q_CS.rotation_matrix),(np.transpose(vsun_S_k[:])/np.linalg.norm(vsun_S_k[:])))
                 
                ## 2.5 ESTIMATE MEASUREMENT:
                print('Iteration ' + str(j) + ': 2.5 ESTIMATE MEASUREMENT')
                vsun_C_k_kminus = np.zeros((3,1))
                vsun_C_aux = np.zeros((3,1))
                
                for s in range(0,2*int(L[1])+1):
                    
                    if s == 0:
                        vsun_C_aux = (np.matmul(Quaternion(vector=Chi_k_kminus[:,s][1:4],scalar=Chi_k_kminus[:,s][0:1]).rotation_matrix,np.reshape((vsun_I_k_kminus/np.linalg.norm(vsun_I_k_kminus)),(3,1))))
                        vsun_C_k_kminus = W_m[0,s]*vsun_C_aux[:,s]
                    else:
                        vsun_C_aux = np.c_[vsun_C_aux,(np.matmul((Quaternion(vector=Chi_k_kminus[:,s][1:4],scalar=Chi_k_kminus[:,s][0:1]).rotation_matrix),np.reshape((vsun_I_k_kminus/np.linalg.norm(vsun_I_k_kminus)),(3,1))))]
                        vsun_C_k_kminus = vsun_C_k_kminus + W_m[0,s]*vsun_C_aux[:,s]
            else:
                ## 2.6 HARDCODE VECTOR:
                print('Iteration ' + str(j) + ': 2.6 HARDCODE VECTOR')
                vsun_C_k = np.zeros((3,1))
                vsun_C_k_kminus = np.zeros((3,1))
                
        elif r == 0:
            ## 2.4 NORMALIZE AND ROTATE:
            print('Iteration ' + str(j) + ': 2.4 NORMALIZE AND ROTATE')
            vsun_C_k = np.zeros((3,1))
                 
            ## 2.5 ESTIMATE MEASUREMENT:
            print('Iteration ' + str(j) + ': 2.5 ESTIMATE MEASUREMENT')
            vsun_C_k_kminus = np.zeros((3,1))
            vsun_C_aux = np.zeros((3,1))
                
            for s in range(0,2*int(L[1])+1):
                    
                if s == 0:
                    vsun_C_aux = (np.matmul(Quaternion(vector=Chi_k_kminus[:,s][1:4],scalar=Chi_k_kminus[:,s][0:1]).rotation_matrix,np.reshape((vsun_I_k_kminus/np.linalg.norm(vsun_I_k_kminus)),(3,1))))
                    vsun_C_k_kminus = W_m[0,s]*vsun_C_aux[:,s]
                else:
                    vsun_C_aux = np.c_[vsun_C_aux,(np.matmul((Quaternion(vector=Chi_k_kminus[:,s][1:4],scalar=Chi_k_kminus[:,s][0:1]).rotation_matrix),np.reshape((vsun_I_k_kminus/np.linalg.norm(vsun_I_k_kminus)),(3,1))))]
                    vsun_C_k_kminus = vsun_C_k_kminus + W_m[0,s]*vsun_C_aux[:,s]
            
            r = 1
                
        elif r == 2:
            ## 2.3 NEW MEASUREMENT?:
            print('Iteration ' + str(j) + ': 2.3 NEW MEASUREMENT?')
            comparison = vmag_S_k_save[j-1] == vmag_S_k_save[j]
            equal_arrays = comparison.all()
            
            if equal_arrays == False:
            
                ## 2.4 NORMALIZE AND ROTATE:
                print('Iteration ' + str(j) + ': 2.4 NORMALIZE AND ROTATE')
                vmag_C_k = np.matmul((q_CS.rotation_matrix),(np.transpose(vmag_S_k[:])/np.linalg.norm(vmag_S_k[:])))
                 
                ## 2.5 ESTIMATE MEASUREMENT:
                print('Iteration ' + str(j) + ': 2.5 ESTIMATE MEASUREMENT')
                vmag_C_k_kminus = np.zeros((3,1))
                vmag_C_aux = np.zeros((3,1))
                
                for s in range(0,2*int(L[1])+1):
                    
                    if s == 0:
                        vmag_C_aux = (np.matmul(Quaternion(vector=Chi_k_kminus[:,s][1:4],scalar=Chi_k_kminus[:,s][0:1]).rotation_matrix,np.reshape((vmag_I_k_kminus/np.linalg.norm(vmag_I_k_kminus)),(3,1))))
                        vmag_C_k_kminus = W_m[0,s]*vmag_C_aux[:,s]
                    else:
                        vmag_C_aux = np.c_[vmag_C_aux,(np.matmul((Quaternion(vector=Chi_k_kminus[:,s][1:4],scalar=Chi_k_kminus[:,s][0:1]).rotation_matrix),np.reshape((vmag_I_k_kminus/np.linalg.norm(vmag_I_k_kminus)),(3,1))))]
                        vmag_C_k_kminus = vmag_C_k_kminus + W_m[0,s]*vmag_C_aux[:,s]
                
            else:
                
                ## 2.6 HARDCODE VECTOR:
                print('Iteration ' + str(j) + ': 2.6 HARDCODE VECTOR')
                vmag_C_k = np.zeros((3,1))
                vmag_C_k_kminus = np.zeros((3,1))
                
        elif r == 3:
            ## 2.3 NEW MEASUREMENT?:
            print('Iteration ' + str(j) + ': 2.3 NEW MEASUREMENT?')
            comparison = omega_S_k_save[j-1] == omega_S_k_save[j]
            equal_arrays = comparison.all()
            
            if equal_arrays == False:
                                
                ## 2.4 NORMALIZE AND ROTATE:
                print('Iteration ' + str(j) + ': 2.4 NORMALIZE AND ROTATE')
                omega_C_k = np.matmul((q_CS.rotation_matrix),omega_S_k)
                 
                ## 2.5 ESTIMATE MEASUREMENT:
                print('Iteration ' + str(j) + ': 2.5 ESTIMATE MEASUREMENT')
                omega_C_k_kminus = np.zeros((3,1))
                omega_C_aux = np.zeros((3,1))
                
                for s in range(0,2*int(L[1])+1):
                    
                    if s == 0:
                        omega_C_aux = (np.matmul(Quaternion(vector=Chi_k_kminus[:,s][1:4],scalar=Chi_k_kminus[:,s][0:1]).rotation_matrix,np.transpose(omega_I_k_kminus)))
                        omega_C_k_kminus = W_m[0,s]*omega_C_aux[:,s]

                    else:
                        omega_C_aux = np.c_[omega_C_aux,(np.matmul((Quaternion(vector=Chi_k_kminus[:,s][1:4],scalar=Chi_k_kminus[:,s][0:1]).rotation_matrix),np.transpose(omega_I_k_kminus)))]
                        omega_C_k_kminus = omega_C_k_kminus + W_m[0,s]*omega_C_aux[:,s]
            
            else:
                
                ## 2.6 HARDCODE VECTOR:
                print('Iteration ' + str(j) + ': 2.6 HARDCODE VECTOR')
                omega_C_k = np.zeros((3,1))
                omega_C_k_kminus = np.zeros((3,1))
            
        r += 1

    ## 2.8 CALCULATE COVARIANCES:
    print('Iteration ' + str(j) + ': 2.8 CALCULATE COVARIANCES')
    P_zk_zk = np.zeros((9,9))
    P_xk_zk = np.zeros((6,9))
    z_k_kminus = np.zeros((9,1))
    
    Z_k_kminus = np.r_[np.r_[vsun_C_aux,vmag_C_aux],omega_C_aux]
    
    for u in range(0,2*int(L[1])+1):
    
        if u == 0:
            z_k_kminus = W_m[0,u]*Z_k_kminus[:,u]
        else:
            z_k_kminus = z_k_kminus + W_m[0,u]*Z_k_kminus[:,u]
            
    for v in range(0,2*int(L[1])+1):
        if v == 0:
            P_xk_zk = W_c[0,v]*np.matmul((np.reshape(Chi_k_kminus[:,v][1:7],(6,1)) - np.reshape(x_k_kminus[0][1:7],(6,1))),np.reshape(np.transpose((Z_k_kminus[:,v] - z_k_kminus)),(1,9)))
            P_zk_zk = W_c[0,v]*np.matmul((Z_k_kminus[:,v] - z_k_kminus),np.transpose((Z_k_kminus[:,v] - z_k_kminus)))
        else:
            P_xk_zk = P_xk_zk + W_c[0,v]*np.matmul((np.reshape(Chi_k_kminus[:,v][1:7],(6,1)) - np.reshape(x_k_kminus[0][1:7],(6,1))),np.reshape(np.transpose((Z_k_kminus[:,v] - z_k_kminus)),(1,9)))
            P_zk_zk = P_zk_zk + W_c[0,v]*np.matmul((Z_k_kminus[:,v] - z_k_kminus),np.transpose((Z_k_kminus[:,v] - z_k_kminus)))
    
    P_zk_zk = P_zk_zk + R
    
    ## 2.9 CALCULATE KALMAN GAIN:
    print('Iteration ' + str(j) + ': 2.9 CALCULATE KALMAN GAIN')
    K_k = np.matmul(P_xk_zk,np.linalg.inv(P_zk_zk))
    
    ## 2.10 CALCULATE QUATERNION ERROR STATE:
    print('Iteration ' + str(j) + ': 2.10 CALCULATE QUATERNION ERROR STATE')
    z_k = np.zeros((9,1))
    z_k = np.r_[np.r_[np.reshape(vsun_C_k,(3,1)),np.reshape(vmag_C_k,(3,1))],np.reshape(omega_C_k,(3,1))]
    
    delx_k_k = np.matmul(K_k,(z_k - np.reshape(z_k_kminus,(9,1))))
    
    ## 2.11 EXPAND QUATERNIONS:
    print('Iteration ' + str(j) + ': 2.11 EXPAND QUATERNIONS')
    
    q_CI_k_kminus = Quaternion(vector=[x_k_kminus[0][1],x_k_kminus[0][2],x_k_kminus[0][3]],scalar=x_k_kminus[0][0])
    q_CI_k_kminus = quaternion_antipod(q_CI,q_CI_k_kminus)
        
    delq_k_k = delx_k_k[0:3]
    delq_in = np.dot(np.transpose(delq_k_k),delq_k_k)[0,0]
    
    delq = Quaternion(vector=delq_k_k,scalar=math.sqrt(math.fabs(1 - delq_in)))
    
    delq = quaternion_antipod(q_CI,delq)
    
    delomega_k_k = (np.reshape(delx_k_kminus,(6,1)) - delx_k_k)[3:6]
    
    q_CI_k_k = delq*q_CI_k_kminus
    
    omega_C_k_k = np.transpose(omega_C_k_kminus)  + np.transpose(delomega_k_k)
    
    ## 2.12 CALCULATE FULL STATE:
    print('Iteration ' + str(j) + ': 2.12 CALCULATE FULL STATE')
    
    x_k_k = np.c_[np.reshape([q_CI_k_k[0],q_CI_k_k[1],q_CI_k_k[2],q_CI_k_k[3]],(1,4)),omega_C_k_k]
    
    ## 2.13 A POSTERIORI COVARIANCE:
    print('Iteration ' + str(j) + ': 2.13 A POSTERIORI COVARIANCE')
    aux_K = (np.matmul(K_k,np.matmul(P_zk_zk,np.transpose(K_k))))
    
    P_k_k = P_k_kminus - aux_K
    
    U,S,V = np.linalg.svd(q_CI_k_k.rotation_matrix)
    
    s1 = S.item(0)
    s2 = S.item(1)
    s3 = np.linalg.det(U)*np.linalg.det(V)*S.item(2)
    
    P = np.matmul((np.matmul(U,np.diag([(s2+s3)**-1, (s3+s1)**-1, (s1+s2)**-1]))),np.transpose(U))
    
    P_sum = math.fabs(P_k_k.item(0,0)+P_k_k.item(0,1)+P_k_k.item(0,2) + P_k_k.item(1,0)+P_k_k.item(1,1)+P_k_k.item(1,2) + P_k_k.item(2,0)+P_k_k.item(2,1)+P_k_k.item(2,2))
    
    P_sum_save = np.r_[P_sum_save,np.reshape(P_sum,(1,1))]
    print('Soma dos elementos da matriz de covariancia: ' + str(P_sum))
    
    ## 2.14 ROTATE AND OUTPUT:
    print('Iteration ' + str(j) + ': 2.14 ROTATE AND OUTPUT')
    aux_Output1 = quaternion_multiply((q_CS.inverse),q_CI_k_k)
    aux_Output2 = np.matmul((q_CS.inverse).rotation_matrix,np.reshape(omega_C_k,(3,1)))
    
    ## CORRECTION OF THE ANTIPODAL PROBLEM
    antipod = q_CI_k_k[0]*q_CI[0] + q_CI_k_k[1]*q_CI[1] + q_CI_k_k[2]*q_CI[2] + q_CI_k_k[3]*q_CI[3]
    if antipod < 0:
        aux_Output1 = -aux_Output1
    
    if j == 1:
        Output = np.array([aux_Output1[0],aux_Output1[1],aux_Output1[2],aux_Output1[3],aux_Output2[0,0],aux_Output2[1,0],aux_Output2[2,0]])
        out_q_CI = np.array([q_CI[0],q_CI[1],q_CI[2],q_CI[3],aux_Output2[0,0],aux_Output2[1,0],aux_Output2[2,0]])
        out_eclipse = np.array([eclipse])
    else:
        Output = np.c_[Output,np.array([aux_Output1[0],aux_Output1[1],aux_Output1[2],aux_Output1[3],aux_Output2[0,0],aux_Output2[1,0],aux_Output2[2,0]])]
        out_q_CI = np.c_[out_q_CI,np.array([q_CI[0],q_CI[1],q_CI[2],q_CI[3],aux_Output2[0,0],aux_Output2[1,0],aux_Output2[2,0]])]
        out_eclipse = np.c_[out_eclipse,np.array([eclipse])]
    
    ###############################################################################
    ################################## UPDATES ####################################
    ###############################################################################
    
    q_CI_kminus_kminus = q_CI_k_k
        
    P_kminus_kminus = P_k_k
    omega_C_kminus_kminus = omega_C_k_k
    
    print('q_CI_k_kminus = ' + str(q_CI_k_kminus))
    print('q_CI_k_k = ' + str(q_CI_k_k))
    print('q_CI = ' + str(q_CI))
    print('delq = ' + str(delq))

#### Início Análises ####

from scipy.spatial.transform import Rotation as Rot

delta = np.zeros((7,len(timer)-1))

for i in range(0,len(timer)-1):
    r = Rot.from_quat(Output[:,i][0:4])
    r_euler = r.as_euler('zxz', degrees=True)
    
    if i == 0:
        Output_Euler = r_euler
        delta[:,i] = np.sqrt((Output[:,i]-out_q_CI[:,i])**2)
    else:
        Output_Euler = np.c_[Output_Euler,r_euler]
        delta[:,i] = np.sqrt((Output[:,i]-out_q_CI[:,i])**2)

from matplotlib import pyplot as plt

fig, (ax1, ax2, ax3) = plt.subplots(3, sharex=True)
ax1.plot(np.transpose(vmag_S_k_save)[:][0],color='r', label='x')
ax1.plot(np.transpose(vmag_S_k_save)[:][1],color='g', label='y')
ax1.plot(np.transpose(vmag_S_k_save)[:][2],color='b', label='z')
ax2.plot(np.transpose(vsun_S_k_save)[:][0],color='r', label='x')
ax2.plot(np.transpose(vsun_S_k_save)[:][1],color='g', label='y')
ax2.plot(np.transpose(vsun_S_k_save)[:][2],color='b', label='z')
ax3.plot(np.transpose(omega_S_k_save)[:][0],color='r', label='x')
ax3.plot(np.transpose(omega_S_k_save)[:][1],color='g', label='y')
ax3.plot(np.transpose(omega_S_k_save)[:][2],color='b', label='z')
fig = plt.gcf()
fig.set_size_inches(18.5, 18.5, forward=True)
plt.xticks(rotation=90)
plt.xlabel('Tempo [*10 s]')
ax1.legend(bbox_to_anchor=(0.95, 1), loc='upper left', borderaxespad=0.)
ax2.legend(bbox_to_anchor=(0.95, 1), loc='upper left', borderaxespad=0.)
ax3.legend(bbox_to_anchor=(0.95, 1), loc='upper left', borderaxespad=0.)
ax1.set(ylabel='Sensor Magnético' + '\n' + 'Componentes do Vetor [µT]')
ax2.set(ylabel='Sensor Solar' + '\n' + 'Componentes do Vetor [Km]')
ax3.set(ylabel='Giroscópio' + '\n' + 'Componentes do Vetor [rad/s]')
plt.savefig('vsensors.png', bbox_inches='tight', dpi=100)
plt.show()

fig, (ax1, ax2, ax3, ax4) = plt.subplots(4)
ax1.plot(Output[1][:],color='k', label='atitude estimada')
ax1.plot(out_q_CI[1][:],color='g', label='atitude real')
ax1.plot(np.transpose(out_eclipse[:]),color='b', label='eclipse (1=sim, 0=não)')
ax1.set(ylabel='Quaternion [q1]')
ax2.plot(Output[2][:],color='k', label='atitude estimada')
ax2.plot(out_q_CI[2][:],color='g', label='atitude real')
ax2.plot(np.transpose(out_eclipse[:]),color='b', label='eclipse (1=sim, 0=não)')
ax2.set(ylabel='Quaternion [q2]')
ax3.plot(Output[3][:],color='k', label='atitude estimada')
ax3.plot(out_q_CI[3][:],color='g', label='atitude real')
ax3.plot(np.transpose(out_eclipse[:]),color='b', label='eclipse (1=sim, 0=não)')
ax3.set(ylabel='Quaternion [q3]')
ax4.plot(Output[0][:],color='k', label='atitude estimada')
ax4.plot(out_q_CI[0][:],color='g', label='atitude real')
ax4.plot(np.transpose(out_eclipse[:]),color='b', label='eclipse (1=sim, 0=não)')
ax1.legend(bbox_to_anchor=(0.85, 1), loc='upper left', borderaxespad=0.)
ax2.legend(bbox_to_anchor=(0.85, 1), loc='upper left', borderaxespad=0.)
ax3.legend(bbox_to_anchor=(0.85, 1), loc='upper left', borderaxespad=0.)
ax4.legend(bbox_to_anchor=(0.85, 1), loc='upper left', borderaxespad=0.)
fig = plt.gcf()
fig.set_size_inches(18.5, 18.5, forward=True)
plt.xticks(rotation=90)
plt.xlabel('Tempo [*10 s]')
ax4.set(ylabel='Quaternion [q4]')
plt.savefig('quat.png', bbox_inches='tight')
plt.show()

fig, (ax1, ax2, ax3, ax4) = plt.subplots(4)
ax1.plot((delta[1,:]),color='k', label='delta')
ax1.plot(np.transpose(out_eclipse[:]),color='b', label='eclipse (1=sim, 0=não)')
ax1.set(ylabel='Delta [q1]')
ax2.plot((delta[2,:]),color='k', label='delta')
ax2.plot(np.transpose(out_eclipse[:]),color='b', label='eclipse (1=sim, 0=não)')
ax2.set(ylabel='Delta [q2]')
ax3.plot((delta[3,:]),color='k', label='delta')
ax3.plot(np.transpose(out_eclipse[:]),color='b', label='eclipse (1=sim, 0=não)')
ax3.set(ylabel='Delta [q3]')
ax4.plot((delta[0,:]),color='k', label='delta')
ax4.plot(np.transpose(out_eclipse[:]),color='b', label='eclipse (1=sim, 0=não)')
ax1.legend(bbox_to_anchor=(0.85, 1), loc='upper left', borderaxespad=0.)
ax2.legend(bbox_to_anchor=(0.85, 1), loc='upper left', borderaxespad=0.)
ax3.legend(bbox_to_anchor=(0.85, 1), loc='upper left', borderaxespad=0.)
ax4.legend(bbox_to_anchor=(0.85, 1), loc='upper left', borderaxespad=0.)
fig = plt.gcf()
fig.set_size_inches(18.5, 18.5, forward=True)
plt.xticks(rotation=90)
plt.xlabel('Tempo [*10 s]')
ax4.set(ylabel='Delta [q4]')
plt.savefig('delta.png', bbox_inches='tight')
plt.show()

plt.plot(P_sum_save,color='k')
fig = plt.gcf()
fig.set_size_inches(18.5, 3.5, forward=True)
plt.xticks(rotation=90)
plt.xlabel('Tempo [*10 s]')
plt.ylabel('P_sum')
plt.savefig('P_sum.png', bbox_inches='tight')
plt.show()

print("--- %s seconds ---" % (time.time() - start_time))
