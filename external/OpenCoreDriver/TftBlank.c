#include "TftBlank.h"

static EFI_GUID gEfiUsbIoProtocolGuid = EFI_USB_IO_PROTOCOL_GUID;

static VOID PrintMessage(EFI_SYSTEM_TABLE *SystemTable, CHAR16 *Msg) {
    if (SystemTable != NULL && SystemTable->ConOut != NULL && SystemTable->ConOut->OutputString != NULL) {
        SystemTable->ConOut->OutputString(SystemTable->ConOut, Msg);
    }
}

EFIAPI
EFI_STATUS
EfiDriverEntryPoint(
    IN EFI_HANDLE           ImageHandle,
    IN EFI_SYSTEM_TABLE     *SystemTable
) {
    EFI_STATUS              Status;
    UINTN                   NoHandles = 0;
    EFI_HANDLE              *Handles = NULL;
    UINTN                   Index;
    BOOLEAN                 DeviceFound = 0;

    (VOID)ImageHandle;

    PrintMessage(SystemTable, L"[TftBlank] Scanning USB devices for Turing Smart Screen...\r\n");

    if (SystemTable == NULL || SystemTable->BootServices == NULL) {
        return EFI_INVALID_PARAMETER;
    }

    Status = SystemTable->BootServices->LocateHandleBuffer(
        ByProtocol,
        &gEfiUsbIoProtocolGuid,
        NULL,
        &NoHandles,
        &Handles
    );

    if (EFI_ERROR(Status) || Handles == NULL || NoHandles == 0) {
        PrintMessage(SystemTable, L"[TftBlank] No USB IO protocols found in UEFI.\r\n");
        return EFI_SUCCESS;
    }

    for (Index = 0; Index < NoHandles; Index++) {
        EFI_USB_IO_PROTOCOL *UsbIo = NULL;

        Status = SystemTable->BootServices->HandleProtocol(
            Handles[Index],
            &gEfiUsbIoProtocolGuid,
            (VOID **)&UsbIo
        );

        if (EFI_ERROR(Status) || UsbIo == NULL) {
            continue;
        }

        EFI_USB_DEVICE_DESCRIPTOR DevDesc;
        Status = UsbIo->UsbGetDeviceDescriptor(UsbIo, &DevDesc);
        if (EFI_ERROR(Status)) {
            continue;
        }

        // Match Turing Smart Screen 3.5" Revision A (WCH CH554 VID: 0x1A86, PID: 0x5722)
        if (DevDesc.IdVendor == 0x1A86 && DevDesc.IdProduct == 0x5722) {
            EFI_USB_INTERFACE_DESCRIPTOR IfDesc;
            Status = UsbIo->UsbGetInterfaceDescriptor(UsbIo, &IfDesc);
            if (EFI_ERROR(Status)) {
                continue;
            }

            UINT8 EpIndex;
            for (EpIndex = 0; EpIndex < IfDesc.NumEndpoints; EpIndex++) {
                EFI_USB_ENDPOINT_DESCRIPTOR EpDesc;
                Status = UsbIo->UsbGetEndpointDescriptor(UsbIo, EpIndex, &EpDesc);
                if (EFI_ERROR(Status)) {
                    continue;
                }

                // Check for Bulk OUT endpoint (Attributes: 0x02 = Bulk, Address MSB: 0 = OUT)
                if ((EpDesc.Attributes & 0x03) == 0x02 && (EpDesc.EndpointAddress & 0x80) == 0) {
                    UINT8 BulkOutEp = EpDesc.EndpointAddress;
                    UINT32 TransferStatus = 0;
                    UINTN Length;

                    DeviceFound = 1;
                    PrintMessage(SystemTable, L"[TftBlank] Found Turing 3.5 display. Blanking panel...\r\n");

                    // 1. Send TO_BLACK (103): Fills frame memory with 0x0000
                    UINT8 cmdBlack[6] = { 0, 0, 0, 0, 0, 103 };
                    Length = sizeof(cmdBlack);
                    UsbIo->UsbBulkTransfer(UsbIo, BulkOutEp, cmdBlack, &Length, 500, &TransferStatus);

                    SystemTable->BootServices->Stall(10000); // 10ms

                    // 2. Send SET_BRIGHTNESS (110) with level_absolute = 255 (0% duty cycle / LED off)
                    // (255 >> 2) = 63 (0x3F), ((255 & 3) << 6) = 192 (0xC0)
                    UINT8 cmdBrightness[6] = { 0x3F, 0xC0, 0, 0, 0, 110 };
                    Length = sizeof(cmdBrightness);
                    UsbIo->UsbBulkTransfer(UsbIo, BulkOutEp, cmdBrightness, &Length, 500, &TransferStatus);

                    SystemTable->BootServices->Stall(10000); // 10ms

                    // 3. Send SCREEN_OFF (108): ST7796 display sleep mode
                    UINT8 cmdScreenOff[6] = { 0, 0, 0, 0, 0, 108 };
                    Length = sizeof(cmdScreenOff);
                    UsbIo->UsbBulkTransfer(UsbIo, BulkOutEp, cmdScreenOff, &Length, 500, &TransferStatus);

                    PrintMessage(SystemTable, L"[TftBlank] Display blanked and backlight extinguished.\r\n");
                    break;
                }
            }
        }
    }

    SystemTable->BootServices->FreePool(Handles);

    if (!DeviceFound) {
        PrintMessage(SystemTable, L"[TftBlank] Device 1a86:5722 not present on this bus scan.\r\n");
    }

    return EFI_SUCCESS;
}
