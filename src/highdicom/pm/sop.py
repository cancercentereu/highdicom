from collections import defaultdict
from typing import cast, Dict, List, Optional, Sequence, Tuple, Union
from enum import Enum

import numpy as np
from pydicom.encaps import encapsulate
from highdicom.base import SOPClass
from highdicom.content import (
    PixelMeasuresSequence,
    PlaneOrientationSequence,
    PlanePositionSequence,
)
from highdicom.enum import CoordinateSystemNames
from highdicom.frame import encode_frame
from highdicom.pm.content import RealWorldValueMapping
from highdicom.pm.content import DimensionIndexSequence
from highdicom.valuerep import check_person_name
from pydicom import Dataset
from pydicom.uid import (
    UID,
    ExplicitVRLittleEndian,
    ImplicitVRLittleEndian,
    JPEG2000Lossless,
    RLELossless,
)


class _PixelDataType(Enum):
    """Helper enum for tracking the type of the pixel data"""

    SHORT = 1
    USHORT = 2
    SINGLE = 3
    DOUBLE = 4


class ParametricMap(SOPClass):

    """SOP class for a Parametric Map."""

    def __init__(
        self,
        source_images: Sequence[Dataset],
        pixel_array: np.ndarray,
        series_instance_uid: str,
        series_number: int,
        sop_instance_uid: str,
        instance_number: int,
        manufacturer: str,
        manufacturer_model_name: str,
        software_versions: Union[str, Tuple[str]],
        device_serial_number: str,
        contains_recognizable_visual_features: bool,
        real_world_value_mappings: Union[
            Sequence[RealWorldValueMapping],
            Sequence[Sequence[RealWorldValueMapping]],
        ],
        window_center: Union[int, float],
        window_width: Union[int, float],
        transfer_syntax_uid: Union[str, UID] = ImplicitVRLittleEndian,
        content_description: Optional[str] = None,
        content_creator_name: Optional[str] = None,
        pixel_measures: Optional[PixelMeasuresSequence] = None,
        plane_orientation: Optional[PlaneOrientationSequence] = None,
        plane_positions: Optional[Sequence[PlanePositionSequence]] = None,
        **kwargs,
    ):
        """

        Parameters
        ----------
        source_images: Sequence[pydicom.dataset.Dataset]
            One or more single- or multi-frame images (or metadata of images)
            from which the parametric map was derived
        pixel_array: numpy.ndarray
            2D, 3D, or 4D array of signed integer, unsigned integer, or
            floating-point data type representing one or more channels
            (images derived from source images via an image transformation)
            for one or more spatial image positions:

            * In case of a 2D array, the values represent a single channel
              for a single 2D frame and the array shall have shape ``(r, c)``,
              where ``r`` is the number of rows and ``c`` is the number of
              columns.

            * In case of a 3D array, the values represent a single channel
              for multiple 2D frames at different spatial image positions and
              the array shall have shape ``(n, r, c)``, where ``n`` is the
              number of frames, ``r`` is the number of rows per frame, and
              ``c`` is the number of columns per frame.

            * In case of a 4D array, the values represent multiple channels
              for multiple 2D frames at different spatial image positions and
              the array shall have shape ``(n, r, c, m)``, where ``n`` is the
              number of frames, ``r`` is the number of rows per frame, ``c`` is
              the number of columns per frame, and ``m`` is the number of
              channels.

        series_instance_uid: str
            UID of the series
        series_number: Union[int, None]
            Number of the series within the study
        sop_instance_uid: str
            UID that should be assigned to the instance
        instance_number: int
            Number that should be assigned to the instance
        manufacturer: str
            Name of the manufacturer (developer) of the device (software)
            that creates the instance
        manufacturer_model_name: str,
            Name of the model of the device (software)
            that creates the instance
        software_versions: Union[str, Tuple[str]]
            Versions of relevant software used to create the data
        device_serial_number: str
            Serial number (or other identifier) of the device (software)
            that creates the instance
        contains_recognizable_visual_features: bool
            Whether the image contains recognizable visible features of the
            patient
        real_world_value_mappings: Union[Sequence[highdicom.map.RealWorldValueMapping], Sequence[Sequence[highdicom.map.RealWorldValueMapping]]
            Descriptions of how stored values map to real-world values.
            Each channel encoded in `pixel_array` shall be described with one
            or more real-world value mappings. Multiple mappings might be
            used for different representations such as log versus linear scales
            or for different representations in different units.
            If `pixel_array` is a 2D or 3D array and only one channel exists
            at each spatial image position), then one or more real-world value
            mappings shall be provided in a flat sequence.
            If `pixel_array` is a 4D array and multiple channels exist at each
            spatial image position, then one or more mappings shall be provided
            for each channel in a nested sequence of length ``m``, where ``m``
            shall match the channel dimension of the `pixel_array``.

            In some situations the mapping may be difficult to describe (e.g., in
            case of a transformation performed by a deep convolutional neural
            network). The real-world value mapping may simply describe an
            identity function that maps stored values to unit-less real-world
            values.
        window_center: Union[int, float, None], optional
            Window center for rescaling stored values for display purposes by
            applying a linear transformation function. For example, in case of
            floating-point values in the range ``[0.0, 1.0]``, the window
            center may be ``0.5``, in case of floating-point values in the
            range ``[-1.0, 1.0]`` the window center may be ``0.0``, in case
            of unsigned integer values in the range ``[0, 255]`` the window
            center may be ``128``.
        window_width: Union[int, float, None], optional
            Window width for rescaling stored values for display purposes by
            applying a linear transformation function. For example, in case of
            floating-point values in the range ``[0.0, 1.0]``, the window
            width may be ``1.0``, in case of floating-point values in the
            range ``[-1.0, 1.0]`` the window width may be ``2.0``, and in
            case of unsigned integer values in the range ``[0, 255]`` the
            window width may be ``256``. In case of unbounded floating-point
            values, a sensible window width should be chosen to allow for
            stored values to be displayed on 8-bit monitors.
        transfer_syntax_uid: Union[str, None], optional
            UID of transfer syntax that should be used for encoding of
            data elements. Defaults to Implicit VR Little Endian
            (UID ``"1.2.840.10008.1.2"``)
        content_description: Union[str, None], optional
            Brief description of the parametric map image
        content_creator_name: Union[str, None], optional
            Name of the person that created the parametric map image
        pixel_measures: Union[highdicom.PixelMeasuresSequence, None], optional
            Physical spacing of image pixels in `pixel_array`.
            If ``None``, it will be assumed that the parametric map image has
            the same pixel measures as the source image(s).
        plane_orientation: Union[highdicom.PlaneOrientationSequence, None], optional
            Orientation of planes in `pixel_array` relative to axes of
            three-dimensional patient or slide coordinate space.
            If ``None``, it will be assumed that the parametric map image as
            the same plane orientation as the source image(s).
        plane_positions: Union[Sequence[PlanePositionSequence], None], optional
            Position of each plane in `pixel_array` in the three-dimensional
            patient or slide coordinate space.
            If ``None``, it will be assumed that the parametric map image has
            the same plane position as the source image(s). However, this will
            only work when the first dimension of `pixel_array` matches the
            number of frames in `source_images` (in case of multi-frame source
            images) or the number of `source_images` (in case of single-frame
            source images).
        **kwargs: Any, optional
            Additional keyword arguments that will be passed to the constructor
            of `highdicom.base.SOPClass`

        Raises
        ------
        ValueError
            When
                * Length of `source_images` is zero.
                * Items of `source_images` are not all part of the same study
                  and series.
                * Items of `source_images` have different number of rows and
                  columns.
                * Length of `plane_positions` does not match number of 2D planes
                  in `pixel_array` (size of first array dimension).
                * Transfer Syntax specified by `transfer_syntax_uid` is not
                  supported for data type of `pixel_array`.

        Note
        ----
        The assumption is made that planes in `pixel_array` are defined in
        the same frame of reference as `source_images`.

        """  # noqa
        if len(source_images) == 0:
            raise ValueError('At least one source image is required')
        self._source_images = source_images

        uniqueness_criteria = set(
            (
                image.StudyInstanceUID,
                image.SeriesInstanceUID,  # TODO: Might be overly restrictive
                image.Rows,
                image.Columns,
                image.FrameOfReferenceUID,
            )
            for image in self._source_images
        )
        if len(uniqueness_criteria) > 1:
            raise ValueError(
                'Source images must all be part of the same series and must'
                'have the same image dimensions (number of rows/columns).'
            )

        src_img = self._source_images[0]
        is_multiframe = hasattr(src_img, 'NumberOfFrames')
        # TODO: Revisit, may be overly restrictive
        # Check Source Image Sequence attribute in General Reference module
        if is_multiframe:
            if len(self._source_images) > 1:
                raise ValueError(
                    'Only one source image should be provided in case images '
                    'are multi-frame images.'
                )
            self._src_num_frames = src_img.NumberOfFrames

        supported_transfer_syntaxes = {
            ImplicitVRLittleEndian,
            ExplicitVRLittleEndian,
        }
        if pixel_array.dtype.kind in ('u', 'i'):
            # If pixel data has unsigned or signed integer data type, then it
            # can be lossless compressed. The standard does not specify any
            # compression codecs for floating-point data types.
            # In case of signed integer data type, values will be rescaled to
            # a signed integer range prior to compression.
            supported_transfer_syntaxes.update(
                {
                    JPEG2000Lossless,
                    RLELossless,
                }
            )
        if transfer_syntax_uid not in supported_transfer_syntaxes:
            raise ValueError(
                f'Transfer syntax "{transfer_syntax_uid}" is not supported.'
            )

        if window_width <= 0:
            raise ValueError('Window width must be greater than zero.')

        if pixel_array.ndim == 2:
            pixel_array = pixel_array[np.newaxis, ...]

        # There are different DICOM Attributes in the SOP instance depending
        # on what type of data is being saved. This lets us keep track of that
        # a bit easier
        self._pixel_data_type_map = {
            _PixelDataType.SHORT: 'PixelData',
            _PixelDataType.USHORT: 'PixelData',
            _PixelDataType.SINGLE: 'FloatPixelData',
            _PixelDataType.DOUBLE: 'DoubleFloatPixelData',
        }

        super().__init__(
            study_instance_uid=src_img.StudyInstanceUID,
            series_instance_uid=series_instance_uid,
            series_number=series_number,
            sop_instance_uid=sop_instance_uid,
            instance_number=instance_number,
            sop_class_uid='1.2.840.10008.5.1.4.1.1.30',
            manufacturer=manufacturer,
            modality='OT',
            transfer_syntax_uid=transfer_syntax_uid,
            patient_id=src_img.PatientID,
            patient_name=src_img.PatientName,
            patient_birth_date=src_img.PatientBirthDate,
            patient_sex=src_img.PatientSex,
            accession_number=src_img.AccessionNumber,
            study_id=src_img.StudyID,
            study_date=src_img.StudyDate,
            study_time=src_img.StudyTime,
            referring_physician_name=getattr(
                src_img, 'ReferringPhysicianName', None
            ),
            **kwargs,
        )

        if hasattr(src_img, 'ImageOrientationSlide') or hasattr(
            src_img, 'ImageCenterPointCoordinatesSequence'
        ):
            coordinate_system = CoordinateSystemNames.SLIDE
        else:
            coordinate_system = CoordinateSystemNames.PATIENT

        # Frame of Reference
        self.FrameOfReferenceUID = src_img.FrameOfReferenceUID
        self.PositionReferenceIndicator = getattr(
            src_img, 'PositionReferenceIndicator', None
        )

        # (Enhanced) General Equipment
        self.DeviceSerialNumber = device_serial_number
        self.ManufacturerModelName = manufacturer_model_name
        self.SoftwareVersions = software_versions

        # General Reference
        self.SourceImageSequence: List[Dataset] = []
        referenced_series: Dict[str, List[Dataset]] = defaultdict(list)
        for s_img in self._source_images:
            ref = Dataset()
            ref.ReferencedSOPClassUID = s_img.SOPClassUID
            ref.ReferencedSOPInstanceUID = s_img.SOPInstanceUID
            self.SourceImageSequence.append(ref)
            referenced_series[s_img.SeriesInstanceUID].append(ref)

        # Common Instance Reference
        self.ReferencedSeriesSequence: List[Dataset] = []
        for (
            series_instance_uid,
            referenced_images,
        ) in referenced_series.items():
            ref = Dataset()
            ref.SeriesInstanceUID = series_instance_uid
            ref.ReferencedInstanceSequence = referenced_images
            self.ReferencedSeriesSequence.append(ref)

        # Parametric Map Image
        self.ImageType = ["DERIVED", "PRIMARY"]
        self.LossyImageCompression = getattr(
            src_img, 'LossyImageCompression', '00'
        )
        if self.LossyImageCompression == "01":
            self.LossyImageCompressionRatio = (
                src_img.LossyImageCompressionRatio
            )
            self.LossyImageCompressionMethod = (
                src_img.LossyImageCompressionMethod
            )
        self.SamplesPerPixel = 1
        self.PhotometricInterpretation = 'MONOCHROME2'
        self.BurnedInAnnotation = 'NO'
        if contains_recognizable_visual_features:
            self.RecognizableVisualFeatures = 'YES'
        else:
            self.RecognizableVisualFeatures = 'NO'
        self.ContentLabel = 'ISO_IR 192'  # UTF-8
        self.ContentDescription = content_description
        if content_creator_name is not None:
            check_person_name(content_creator_name)
        self.ContentCreatorName = content_creator_name
        self.PresentationLUTShape = 'IDENTITY'

        # TODO: check that physical dimensions of the image match those of the
        # source image

        self.DimensionIndexSequence = DimensionIndexSequence(coordinate_system)
        dimension_organization = Dataset()
        dimension_organization.DimensionOrganizationUID = (
            self.DimensionIndexSequence[0].DimensionOrganizationUID
        )
        self.DimensionOrganizationSequence = [dimension_organization]

        sffg_item = Dataset()

        # If the same set of mappings applies to all frames, the information
        # is stored in the Shared Functional Groups Sequence. Otherwise, it
        # is stored for each frame separately in the Per Frame Functional
        # Groups Sequence.
        if pixel_array.ndim in (2, 3):
            error_message = (
                'In case argument "pixel_array" is a 2D or 3D array, argument '
                '"real_world_value_mappings" must be a flat sequence '
                'of one or more RealWorldValueMapping items.'
            )
            sffg_item.RealWorldValueMappingSequence = real_world_value_mappings
            try:
                real_world_value_mappings[0]
            except IndexError:
                raise TypeError(error_message)
            if not isinstance(
                real_world_value_mappings[0],
                RealWorldValueMapping
            ):
                raise TypeError(error_message)
            if pixel_array.ndim == 2:
                pixel_array = pixel_array[np.newaxis, ..., np.newaxis]
            elif pixel_array.ndim == 3:
                pixel_array = pixel_array[..., np.newaxis]
            real_world_value_mappings = cast(
                Sequence[Sequence[RealWorldValueMapping]],
                [real_world_value_mappings]
            )
        elif pixel_array.ndim == 4:
            error_message = (
                'In case argument "pixel_array" is a 4D array, argument '
                '"real_world_value_mappings" must be a nested sequence '
                'of one or more RealWorldValueMapping items.'
            )
            try:
                real_world_value_mappings[0][0]
            except IndexError:
                raise TypeError(error_message)
            if not isinstance(
                real_world_value_mappings[0][0],
                RealWorldValueMapping
            ):
                raise TypeError(error_message)
            real_world_value_mappings = cast(
                Sequence[Sequence[RealWorldValueMapping]],
                real_world_value_mappings
            )
        else:
            raise ValueError('Pixel array must be a 2D, 3D, or 4D array.')

        # Image Pixel
        self.Rows = pixel_array.shape[1]
        self.Columns = pixel_array.shape[2]

        if len(real_world_value_mappings) != pixel_array.shape[3]:
            raise ValueError(
                'Number of RealWorldValueMapping items provided via '
                '"real_world_value_mappings" argument does not match size of '
                'last dimension of "pixel_array" argument.'
            )

        if plane_positions is None:
            if is_multiframe:
                plane_positions = \
                    self.DimensionIndexSequence.get_plane_positions_of_image(
                        self._source_images[0]
                    )
            else:
                plane_positions = \
                    self.DimensionIndexSequence.get_plane_positions_of_series(
                        self._source_images
                    )
            if len(plane_positions) != pixel_array.shape[0]:
                raise ValueError(
                    'Number of plane positions in source image(s) does not '
                    'match size of first dimension of "pixel_array" argument.'
                )
        else:
            if len(plane_positions) != pixel_array.shape[0]:
                raise ValueError(
                    'Number of PlanePositionSequence items provided via '
                    '"plane_positions" argument does not match size of '
                    'first dimension of "pixel_array" argument.'
                )

        # Multi-Frame Functional Groups and Multi-Frame Dimensions
        if pixel_measures is None:
            if is_multiframe:
                src_shared_fg = src_img.SharedFunctionalGroupsSequence[0]
                pixel_measures = src_shared_fg.PixelMeasuresSequence
            else:
                pixel_measures = PixelMeasuresSequence(
                    pixel_spacing=[float(v) for v in src_img.PixelSpacing],
                    slice_thickness=float(src_img.SliceThickness),
                    spacing_between_slices=src_img.get(
                        'SpacingBetweenSlices', None
                    ),
                )

        if is_multiframe:
            if coordinate_system == CoordinateSystemNames.SLIDE:
                source_plane_orientation = PlaneOrientationSequence(
                    coordinate_system=coordinate_system,
                    image_orientation=[
                        float(v) for v in src_img.ImageOrientationSlide
                    ],
                )
            else:
                src_sfg = src_img.SharedFunctionalGroupsSequence[0]
                source_plane_orientation = src_sfg.PlaneOrientationSequence
        else:
            source_plane_orientation = PlaneOrientationSequence(
                coordinate_system=coordinate_system,
                image_orientation=[
                    float(v) for v in src_img.ImageOrientationPatient
                ],
            )
        if plane_orientation is None:
            plane_orientation = source_plane_orientation

        sffg_item.PixelMeasuresSequence = pixel_measures
        sffg_item.PlaneOrientationSequence = plane_orientation

        # Identity Pixel Value Transformation
        if pixel_array.dtype.kind == 'i':
            # In case of signed integer type we rescale values to unsigned
            # 16-bit integer range.
            transformation_item = Dataset()
            transformation_item.RescaleIntercept = 2 ** 16 / 2
            transformation_item.RescaleSlope = 1
            transformation_item.RescaleType = 'US'
        else:
            transformation_item = Dataset()
            transformation_item.RescaleIntercept = 0
            transformation_item.RescaleSlope = 1
            transformation_item.RescaleType = 'US'
        sffg_item.PixelValueTransformationSequence = [transformation_item]

        # Frame VOI LUT With LUT
        voi_lut_item = Dataset()
        voi_lut_item.WindowCenter = window_center
        voi_lut_item.WindowWidth = window_width
        voi_lut_item.VOILUTFunction = "LINEAR_EXACT"
        sffg_item.FrameVOILUTSequence = [voi_lut_item]

        # Parametric Map Frame Type
        frame_type_item = Dataset()
        frame_type_item.FrameType = self.ImageType
        sffg_item.ParametricMapFrameTypeSequence = [frame_type_item]

        # TODO: put Real World Value Mapping Sequence into shared
        self.SharedFunctionalGroupsSequence = [sffg_item]

        # Get the correct attribute for this Instance's pixel data
        pixel_data_type, pixel_data_attr = self._get_pixel_data_type_and_attr(
            pixel_array
        )
        if (pixel_data_type == _PixelDataType.SHORT or
                pixel_data_type == _PixelDataType.USHORT):
            self.BitsAllocated = 16
            self.BitsStored = self.BitsAllocated
            self.HighBit = self.BitsStored - 1
            self.PixelRepresentation = 0
        elif pixel_data_type == _PixelDataType.SINGLE:
            self.BitsAllocated = 32
        elif pixel_data_type == _PixelDataType.DOUBLE:
            self.BitsAllocated = 64

        self.copy_specimen_information(src_img)
        self.copy_patient_and_study_information(src_img)

        frames, per_frame_func_groups = self._create_frame_items(
            pixel_array,
            pixel_data_type=pixel_data_type,
            real_world_value_mappings=real_world_value_mappings,
            coordinate_system=coordinate_system,
            plane_positions=plane_positions
        )
        self.NumberOfFrames = len(frames)
        self.PerFrameFunctionalGroupsSequence = per_frame_func_groups

        if self.file_meta.TransferSyntaxUID.is_encapsulated:
            pixel_data = encapsulate(frames)
        else:
            pixel_data = b''.join(frames)
        setattr(self, pixel_data_attr, pixel_data)

    def _create_frame_items(
        self,
        pixel_array: np.ndarray,
        pixel_data_type: _PixelDataType,
        real_world_value_mappings: Sequence[Sequence[RealWorldValueMapping]],
        coordinate_system: CoordinateSystemNames,
        plane_positions: Sequence[PlanePositionSequence],
    ) -> Tuple[List[bytes], List[Dataset]]:
        """Create frame items.

        Parameters
        ----------
        pixel_array: np.ndarray
            4D array of unsigned integer or floating-point data type
            with shape ``(n, r, c, m)``, where ``n`` is the number of frames,
            ``r`` is the number of rows per frame, ``c`` is the number of
            columns per frame, and ``m`` is the number of mapping results per
            frame (spatial image position).
        real_world_value_mappings: Sequence[Sequence[highdicom.map.RealWorldValueMappingSequence]]
            Descriptions of the mapping of values stored in `pixel_array` to
            real-world values. One or more descriptions may be provided for
            each mapping result in `pixel_array` (last ``m`` dimension).
        plane_positions: Sequence[highdicom.PlanePositionSequence]
            Position of each plane (frame) in `pixel_array` (first ``n``
            dimension) relative to the patient or slide coordinate system.

        Returns
        -------
        frames: List[bytes]
            Encoded pixel data frames
        per_frame_functional_groups_sequence: List[pydicom.dataset.Dataset]
            Functional groups for each frame

        """  # noqa
        _, spatial_index_values = self.DimensionIndexSequence.get_index_values(
            plane_positions
        )
        per_frame_functional_groups = []
        frames = []
        has_multiple_mappings = pixel_array.shape[3] > 1
        for i in range(pixel_array.shape[0]):
            for j in range(pixel_array.shape[3]):
                pffg_item = Dataset()

                # Derivation Image
                pffg_item.DerivationImageSequence = []

                # Plane Position (Patient/Slide)
                if coordinate_system == CoordinateSystemNames.SLIDE:
                    pffg_item.PlanePositionSlideSequence = plane_positions[i]
                else:
                    pffg_item.PlanePositionSequence = plane_positions[i]

                # Frame Content
                frame_content_item = Dataset()
                frame_content_item.DimensionIndexValues = \
                    spatial_index_values[i, ...].tolist()
                pffg_item.FrameContentSequence = [frame_content_item]

                # Real World Value Mapping
                if has_multiple_mappings:
                    # Only if there are multiple sets of mappings. Otherwise,
                    # the information will be stored in the Shared Functional
                    # Groups Sequence.
                    pffg_item.RealWorldValueMappingSequence = \
                        real_world_value_mappings[j]

                per_frame_functional_groups.append(pffg_item)

                plane = pixel_array[i, :, :, j]
                frames.append(self._encode_frame(plane))

        return (frames, per_frame_functional_groups)

    def _get_pixel_data_type_and_attr(
        self,
        pixel_array: np.ndarray
    ) -> Tuple[_PixelDataType, str]:
        """Get the data type and name of pixel data attribute.

        Parameters
        ----------
        pixel_array : np.ndarray
            The array to check

        Returns
        -------
        Tuple[highdicom.map.sop._PixelDataType, str]
            A tuple where the first element is the enum value and the second
            value is the DICOM pixel data attribute for the given datatype.
            One of (``"PixelData"``, ``"FloatPixelData"``,
            ``"DoubleFloatPixelData"``)

        Raises
        ------
        ValueError
            If values in the input array don't have a supported unsigned
            integer or floating-point type.

        """
        if pixel_array.dtype.kind == 'f':
            # Further check for float32 vs float64
            if pixel_array.dtype.name == 'float32':
                return (
                    _PixelDataType.SINGLE,
                    self._pixel_data_type_map[_PixelDataType.SINGLE],
                )
            elif pixel_array.dtype.name == 'float64':
                return (
                    _PixelDataType.DOUBLE,
                    self._pixel_data_type_map[_PixelDataType.DOUBLE],
                )
            else:
                raise ValueError(
                    'Unsupported floating-point type for pixel data: '
                    '32-bit (single-precision) or 64-bit (double-precision) '
                    'floating-point types are supported.'
                )
        elif pixel_array.dtype.kind == 'u':
            if pixel_array.dtype not in (np.uint8, np.uint16):
                raise ValueError(
                    'Unsupported unsigned integer type for pixel data: '
                    '16-bit unsigned integer types are supported.'
                )
            return (
                _PixelDataType.USHORT,
                self._pixel_data_type_map[_PixelDataType.USHORT],
            )
        elif pixel_array.dtype.kind == "i":
            if pixel_array.dtype not in (np.int8, np.int16):
                raise ValueError(
                    'Unsupported signed integer type for pixel data: '
                    '8-bit or 16-bit signed integer types are supported.'
                )
            return (
                _PixelDataType.SHORT,
                self._pixel_data_type_map[_PixelDataType.SHORT],
            )
        raise ValueError(
            'Unsupported data type for pixel data.'
            'Supported are 8-bit or 16-bit signed and unsigned integer types '
            'as well as 32-bit (single-precision) or 64-bit (double-precision) '
            'floating-point types.'
        )

    def _encode_frame(self, pixel_array: np.ndarray) -> bytes:
        """Encode a given pixel array.

        Parameters
        ----------
        pixel_array: np.ndarray
            The pixel array to encode

        Returns
        -------
        bytes
            Encoded frame

        Raises
        ------
        ValueError
            If the `pixel_array` is not exactly two-dimensional.

        """
        if pixel_array.ndim != 2:
            raise ValueError(
                'Only single frame can be encoded at at time '
                'in case of encapsulated format encoding.'
            )
        if self.file_meta.TransferSyntaxUID.is_encapsulated:
            # Check that only a single plane was passed
            return encode_frame(
                pixel_array.astype(np.uint16),
                transfer_syntax_uid=self.file_meta.TransferSyntaxUID,
                bits_allocated=self.BitsAllocated,
                bits_stored=self.BitsStored,
                photometric_interpretation=self.PhotometricInterpretation,
                pixel_representation=self.PixelRepresentation
            )
        else:
            if pixel_array.dtype == np.uint8:
                return pixel_array.astype(np.uint16).flatten().tobytes()
            elif pixel_array.dtype.kind == 'i':
                pixel_array = pixel_array.astype(np.int16) + 2 ** 16 / 2
                return pixel_array.astype(np.uint16).flatten().tobytes()
            else:
                return pixel_array.flatten().tobytes()
