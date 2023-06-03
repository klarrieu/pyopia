'''
Module for managing the PyOpia processing pipeline

Refer to :class:`Pipeline` for examples of how to process datasets and images
'''
from typing import TypedDict
import datetime
import pandas as pd


class Pipeline():
    '''The processing pipeline class
    ================================

    The classes called in the Pipeline steps can be modified, and the names of the steps changed.
    New steps can be added or deleted as required.

    The classes called in the Pipeline steps need to take a dictionary as input and return a dictionary as output.
    This common dictionary: :class:`pyopia.pipeline.Data` is therefore passed between steps so that data
    or variables generated by each step can be passed along the pipeline.

    By default, the step name: `classifier` is run when initialising `Pipeline`.
    The remaining steps will be run on Pipeline.run().
    You can add initial steps with the optional input `initial_steps`,
    which takes a list of strings of the step key names that should only be run on initialisation of the pipeline.

    The step called 'classifier' must return a dict containing:
    :attr:`pyopia.pipeline.Data.cl` in order to run successfully.

    `Pipeline.run()` takes a string as input.
    This string is put into the `data` dict available to the steps in the pipeline as `data['filename']`.
    This is intended for use in looping through several files during processing, so run can be
    called multiple times with different filenames.

    Examples:
    ^^^^^^^^^

    A holographic processing pipeline:
    """"""""""""""""""""""""""""""""""

    .. code-block:: python

        datafile_hdf = 'proc/holotest'
        model_path = exampledata.get_example_model()
        threshold = 0.9

        average_window = 10  # number of images to use as background

        files = glob(os.path.join(foldername, '*.pgm')) # creates list of files in previously defined folder
        bgfiles = files[:average_window]

        holo_initial_settings = {'pixel_size': 4.4,  # pixel size in um
                                 'wavelength': 658,  # laser wavelength in nm
                                 'n': 1.33,  # index of refraction of sample volume medium (1.33 for water)
                                 'offset': 27,  # offset to start of sample volume in mm
                                 'minZ': 22,  # minimum reconstruction distance in mm
                                 'maxZ': 60,  # maximum reconstruction distance in mm
                                 'stepZ': 0.5}  # step size in mm

        steps = {'initial': holo.Initial(files[0], **holo_initial_settings), # initialisation step to create reconstruction kernel
                'classifier': Classify(model_path=model_path),
                'create background': pyopia.background.CreateBackground(bgfiles,
                                                                        pyopia.instrument.holo.load_image),
                'load': holo.Load(),
                'correct background': pyopia.background.CorrectBackgroundAccurate(pyopia.background.shift_bgstack_accurate),
                'reconstruct': holo.Reconstruct(stack_clean=0.02),
                'focus': holo.Focus(pyopia.instrument.holo.std_map,threshold=threshold),
                'segmentation': pyopia.process.Segment(threshold=threshold),
                'statextract': pyopia.process.CalculateStats(export_outputpath="proc"),
                'output': pyopia.io.StatsH5(datafile_hdf)
                }

        processing_pipeline = Pipeline(steps)

    A silcam processing pipeline:
    """""""""""""""""""""""""""""

    .. code-block:: python

        datafile_hdf = 'proc/test'
        model_path = exampledata.get_example_model()
        threshold = 0.85

        steps = {'classifier': Classify(model_path=model_path),
                 'load': SilCamLoad(),
                 'imageprep': ImagePrep(),
                 'segmentation': pyopia.process.Segment(threshold=threshold),
                 'statextract': pyopia.process.CalculateStats(),
                 'output': pyopia.io.StatsH5(datafile_hdf)}

        # initialise the pipeline with a only the 'classifier' initialisation step:
        processing_pipeline = Pipeline(steps, initial_steps=['classifier'])

    A standard set of silcam analysis setps can be loaded using:
    :func:`pyopia.instrument.silcam.silcam_steps`

    Running a pipeline:
    """""""""""""""""""

    .. code-block:: python

        stats = processing_pipeline.run(filename)


    You can check the workflow used by reading the steps from the metadata in output file, like this:

    .. code-block:: python

        pyopia.io.show_h5_meta(datafile_hdf + '-STATS.h5')



    '''

    def __init__(self, steps, initial_steps=['initial', 'classifier', 'create background']):

        self.initial_steps = initial_steps
        print('Initialising pipeline')
        self.data = Data()
        self.steps = steps

        for s in self.steps:
            if not self.initial_steps.__contains__(s):
                continue
            if s == 'classifier':
                print('  Running', self.steps['classifier'])
                self.data['cl'] = self.steps['classifier']()
            else:
                print('  Running', self.steps[s])
                self.data = self.steps[s](self.data)

        print('Pipeline ready with these data: ', list(self.data.keys()))

    def run(self, filename):
        '''Method for executing the processing pipeline

        Args:
            filename (str): file to be processed

        Returns:
            stats (DataFrame): stats DataFrame of particle statistics
        '''

        self.data['filename'] = filename

        self.data['steps_string'] = steps_to_string(self.steps)

        for s in self.steps:
            if self.initial_steps.__contains__(s):
                continue

            print('calling: ', str(type(self.steps[s])), ' with: ', list(self.data.keys()))
            self.data = self.steps[s](self.data)

        stats = self.data['stats']

        return stats

    def print_steps(self):
        '''Print the steps dictionary
        '''

        # an eventual metadata parser could replace this below printing
        # and format into an appropriate standard
        print('\n-- Pipeline configuration --\n')
        from pyopia import __version__ as pyopia_version
        print('PyOpia version: ' + pyopia_version + '\n')
        print(steps_to_string(self.steps))
        print('\n---------------------------------\n')


class Data(TypedDict):
    '''Data dictionary which is passed between :class:`pyopia.pipeline` steps.

    For debugging, you can use :class:`pyopia.pipeline.ReturnData`
    at the end of a steps dictionary to return of this Data dictionary
    for exploratory purposes.

    In future this may be better as a data class with slots (from python 3.10).

    This is an example of a link to the imc key doc:
    :attr:`pyopia.pipeline.Data.imc`
    '''

    imraw: float
    '''Raw uncorrected image'''
    img: float
    '''Raw uncorrected image. To be deprecatied and changed to imraw'''
    imc: float
    '''Single composite image of focussed particles ready for segmentation
    Obtained from e.g. :class:`pyopia.background.CorrectBackgroundAccurate`
    '''
    bgstack: float
    '''List of images making up the background (either static or moving)
    Obtained from :class:`pyopia.background.CreateBackground`
    '''
    imbg: float
    '''Background image that can be used to correct :attr:`pyopia.pipeline.Data.imraw`
    and calcaulte :attr:`pyopia.pipeline.Data.imc`
    Obtained from :class:`pyopia.background.CreateBackground`
    '''
    filename: str
    '''Filename string'''
    steps_string: str
    '''String documenting the steps given to :class:`pyopia.pipeline`
    This is put here for documentation purposes, and saving as metadata.
    '''
    cl: object
    '''classifier object from :class:`pyopia.classify.Classify`'''
    timestamp: datetime.datetime
    '''timestamp from e.g. :func:`pyopia.instrument.silcam.timestamp_from_filename()`'''
    imbw: float
    '''Segmented binary image identifying particles from water
    Obtained from e.g. :class:`pyopia.process.Segment`
    '''
    stats: pd.DataFrame
    '''stats DataFrame containing particle statistics of every particle
    Obtained from e.g. :class:`pyopia.process.CalculateStats`
    '''
    im_stack: float
    '''3-d array of reconstructed real hologram images
    Obtained from :class:`pyopia.instrument.holo.Reconstruct`
    '''
    imss: float
    '''Stack summary image used to locate possible particles
    Obtained from :class:`pyopia.instrument.holo.Focus`
    '''


def steps_to_string(steps):
    '''Convert pipeline steps dictionary to a human-readable string

    Args:
        steps (dict): pipeline steps dictionary

    Returns:
        str: human-readable string of the types and variables
    '''

    steps_str = '\n'
    for i, key in enumerate(steps.keys()):
        steps_str += (str(i + 1) + ') Step: ' + key
                      + '\n   Type: ' + str(type(steps[key]))
                      + '\n   Vars: ' + str(vars(steps[key]))
                      + '\n')
    return steps_str


class ReturnData():
    '''Pipeline compatible class that can be used for debugging
    if inserted as the last step in the steps dict.


    Pipeline input data:
    --------------------
    :class:`pyopia.pipeline.Data`

    containing any set of keys

    Returns:
    --------
    :class:`pyopia.pipeline.Data`

    Example use:
    ------------

    This will allow you to call pipeline.run() like this:

    .. code-block:: python

        data = pipeline.run(filename)

    where `data` will be the available data dictionary available at the point of calling this
    '''

    def __init__(self):
        pass

    def __call__(self, data):
        data['stats'] = data
        return data
