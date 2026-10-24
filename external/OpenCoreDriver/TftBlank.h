#ifndef _TFT_BLANK_H_
#define _TFT_BLANK_H_

#define EFIAPI __attribute__((ms_abi))

#ifndef NULL
#define NULL ((VOID *)0)
#endif

#ifndef IN
#define IN
#endif

#ifndef OUT
#define OUT
#endif

#ifndef OPTIONAL
#define OPTIONAL
#endif

typedef unsigned char       BOOLEAN;
typedef unsigned char       UINT8;
typedef unsigned short      UINT16;
typedef unsigned int        UINT32;
typedef unsigned long long  UINT64;
typedef signed char         INT8;
typedef signed short        INT16;
typedef signed int          INT32;
typedef signed long long    INT64;
typedef UINT64              UINTN;
typedef INT64               INTN;
typedef UINT16              CHAR16;
typedef void                VOID;

typedef UINTN               EFI_STATUS;
typedef VOID*               EFI_HANDLE;

#define EFI_SUCCESS                 0
#define EFI_LOAD_ERROR              (0x8000000000000001ULL)
#define EFI_INVALID_PARAMETER       (0x8000000000000002ULL)
#define EFI_UNSUPPORTED             (0x8000000000000003ULL)
#define EFI_NOT_FOUND               (0x800000000000000EULL)
#define EFI_TIMEOUT                 (0x8000000000000012ULL)
#define EFI_DEVICE_ERROR            (0x8000000000000007ULL)

#define EFI_ERROR(status)           (((INTN)(status)) < 0)

typedef struct {
    UINT32  Data1;
    UINT16  Data2;
    UINT16  Data3;
    UINT8   Data4[8];
} EFI_GUID;

#define EFI_USB_IO_PROTOCOL_GUID \
    { 0x2B2F68D6, 0x0CD2, 0x44cf, { 0x8E, 0x8B, 0xBB, 0xA0, 0x0B, 0x1B, 0x5B, 0x75 } }

typedef enum {
    AllHandles,
    ByRegisterNotify,
    ByProtocol
} EFI_LOCATE_SEARCH_TYPE;

typedef struct {
    UINT64  Signature;
    UINT32  Revision;
    UINT32  HeaderSize;
    UINT32  CRC32;
    UINT32  Reserved;
} EFI_TABLE_HEADER;

typedef struct _EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL;

typedef EFI_STATUS (EFIAPI *EFI_TEXT_STRING) (
    EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL *This,
    CHAR16                          *String
);

struct _EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL {
    VOID            *Reset;
    EFI_TEXT_STRING OutputString;
    VOID            *TestString;
    VOID            *QueryMode;
    VOID            *SetMode;
    VOID            *SetAttribute;
    VOID            *ClearScreen;
    VOID            *SetCursorPosition;
    VOID            *EnableCursor;
    VOID            *Mode;
};

typedef struct _EFI_USB_IO_PROTOCOL EFI_USB_IO_PROTOCOL;

typedef struct {
    UINT8   RequestType;
    UINT8   Request;
    UINT16  Value;
    UINT16  Index;
    UINT16  Length;
} EFI_USB_DEVICE_REQUEST;

typedef enum {
    EfiUsbDataIn,
    EfiUsbDataOut,
    EfiUsbNoData
} EFI_USB_DATA_DIRECTION;

typedef struct {
    UINT8   Length;
    UINT8   DescriptorType;
    UINT16  BcdUSB;
    UINT8   DeviceClass;
    UINT8   DeviceSubClass;
    UINT8   DeviceProtocol;
    UINT8   MaxPacketSize0;
    UINT16  IdVendor;
    UINT16  IdProduct;
    UINT16  BcdDevice;
    UINT8   StrManufacturer;
    UINT8   StrProduct;
    UINT8   StrSerialNumber;
    UINT8   NumConfigurations;
} __attribute__((packed)) EFI_USB_DEVICE_DESCRIPTOR;

typedef struct {
    UINT8   Length;
    UINT8   DescriptorType;
    UINT8   InterfaceNumber;
    UINT8   AlternateSetting;
    UINT8   NumEndpoints;
    UINT8   InterfaceClass;
    UINT8   InterfaceSubClass;
    UINT8   InterfaceProtocol;
    UINT8   Interface;
} __attribute__((packed)) EFI_USB_INTERFACE_DESCRIPTOR;

typedef struct {
    UINT8   Length;
    UINT8   DescriptorType;
    UINT8   EndpointAddress;
    UINT8   Attributes;
    UINT16  MaxPacketSize;
    UINT8   Interval;
} __attribute__((packed)) EFI_USB_ENDPOINT_DESCRIPTOR;

typedef EFI_STATUS (EFIAPI *EFI_USB_IO_CONTROL_TRANSFER) (
    EFI_USB_IO_PROTOCOL     *This,
    EFI_USB_DEVICE_REQUEST  *Request,
    EFI_USB_DATA_DIRECTION  Direction,
    UINT32                  Timeout,
    VOID                    *Data,
    UINTN                   DataLength,
    UINT32                  *Status
);

typedef EFI_STATUS (EFIAPI *EFI_USB_IO_BULK_TRANSFER) (
    EFI_USB_IO_PROTOCOL *This,
    UINT8               DeviceEndpoint,
    VOID                *Data,
    UINTN               *DataLength,
    UINTN               Timeout,
    UINT32              *Status
);

typedef EFI_STATUS (EFIAPI *EFI_USB_IO_GET_DEVICE_DESCRIPTOR) (
    EFI_USB_IO_PROTOCOL         *This,
    EFI_USB_DEVICE_DESCRIPTOR   *Descriptor
);

typedef EFI_STATUS (EFIAPI *EFI_USB_IO_GET_INTERFACE_DESCRIPTOR) (
    EFI_USB_IO_PROTOCOL             *This,
    EFI_USB_INTERFACE_DESCRIPTOR   *Descriptor
);

typedef EFI_STATUS (EFIAPI *EFI_USB_IO_GET_ENDPOINT_DESCRIPTOR) (
    EFI_USB_IO_PROTOCOL             *This,
    UINT8                           EndpointIndex,
    EFI_USB_ENDPOINT_DESCRIPTOR     *Descriptor
);

struct _EFI_USB_IO_PROTOCOL {
    EFI_USB_IO_CONTROL_TRANSFER         UsbControlTransfer;
    EFI_USB_IO_BULK_TRANSFER            UsbBulkTransfer;
    VOID                                *UsbAsyncInterruptTransfer;
    VOID                                *UsbSyncInterruptTransfer;
    VOID                                *UsbIsochronousTransfer;
    VOID                                *UsbAsyncIsochronousTransfer;
    EFI_USB_IO_GET_DEVICE_DESCRIPTOR    UsbGetDeviceDescriptor;
    VOID                                *UsbGetConfigDescriptor;
    EFI_USB_IO_GET_INTERFACE_DESCRIPTOR UsbGetInterfaceDescriptor;
    EFI_USB_IO_GET_ENDPOINT_DESCRIPTOR  UsbGetEndpointDescriptor;
    VOID                                *UsbGetStringDescriptor;
    VOID                                *UsbPortReset;
};

typedef struct _EFI_BOOT_SERVICES {
    EFI_TABLE_HEADER                Hdr;
    VOID                            *RaiseTPL;
    VOID                            *LowerTPL;
    VOID                            *AllocatePages;
    VOID                            *FreePages;
    VOID                            *GetMemoryMap;
    VOID                            *AllocatePool;
    EFI_STATUS (EFIAPI *FreePool) (
        VOID *Buffer
    );
    VOID                            *CreateEvent;
    VOID                            *SetTimer;
    VOID                            *WaitForEvent;
    VOID                            *SignalEvent;
    VOID                            *CloseEvent;
    VOID                            *CheckEvent;
    VOID                            *InstallProtocolInterface;
    VOID                            *ReinstallProtocolInterface;
    VOID                            *UninstallProtocolInterface;
    EFI_STATUS (EFIAPI *HandleProtocol) (
        EFI_HANDLE Handle,
        EFI_GUID   *Protocol,
        VOID       **Interface
    );
    VOID                            *Reserved;
    VOID                            *RegisterProtocolNotify;
    VOID                            *LocateHandle;
    VOID                            *LocateDevicePath;
    VOID                            *InstallConfigurationTable;
    VOID                            *LoadImage;
    VOID                            *StartImage;
    VOID                            *Exit;
    VOID                            *UnloadImage;
    VOID                            *ExitBootServices;
    VOID                            *GetNextMonotonicCount;
    EFI_STATUS (EFIAPI *Stall) (
        UINTN Microseconds
    );
    VOID                            *SetWatchdogTimer;
    VOID                            *ConnectController;
    VOID                            *DisconnectController;
    VOID                            *OpenProtocol;
    VOID                            *CloseProtocol;
    VOID                            *OpenProtocolInformation;
    VOID                            *ProtocolsPerHandle;
    EFI_STATUS (EFIAPI *LocateHandleBuffer) (
        EFI_LOCATE_SEARCH_TYPE SearchType,
        EFI_GUID               *Protocol,
        VOID                   *SearchKey,
        UINTN                  *NoHandles,
        EFI_HANDLE             **Buffer
    );
    VOID                            *LocateProtocol;
    VOID                            *InstallMultipleProtocolInterfaces;
    VOID                            *UninstallMultipleProtocolInterfaces;
    VOID                            *CalculateCrc32;
    VOID                            *CopyMem;
    VOID                            *SetMem;
    VOID                            *CreateEventEx;
} EFI_BOOT_SERVICES;

typedef struct _EFI_SYSTEM_TABLE {
    EFI_TABLE_HEADER                Hdr;
    CHAR16                          *FirmwareVendor;
    UINT32                          FirmwareRevision;
    EFI_HANDLE                      ConsoleInHandle;
    VOID                            *ConIn;
    EFI_HANDLE                      ConsoleOutHandle;
    EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL *ConOut;
    EFI_HANDLE                      StandardErrorHandle;
    EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL *StdErr;
    VOID                            *RuntimeServices;
    EFI_BOOT_SERVICES               *BootServices;
    UINTN                           NumberOfTableEntries;
    VOID                            *ConfigurationTable;
} EFI_SYSTEM_TABLE;

#endif
