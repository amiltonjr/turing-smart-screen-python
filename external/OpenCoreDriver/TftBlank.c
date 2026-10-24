#include "TftBlank.h"

static EFI_GUID gEfiUsbIoProtocolGuid = EFI_USB_IO_PROTOCOL_GUID;
static EFI_GUID gEfiLoadedImageProtocolGuid = EFI_LOADED_IMAGE_PROTOCOL_GUID;

// Default: silent mode (verbose = false)
static BOOLEAN gVerbose = 0;

static VOID PrintMessage(EFI_SYSTEM_TABLE *SystemTable, CHAR16 *Msg) {
    if (gVerbose && SystemTable != NULL && SystemTable->ConOut != NULL && SystemTable->ConOut->OutputString != NULL) {
        SystemTable->ConOut->OutputString(SystemTable->ConOut, Msg);
    }
}

static VOID PrintNumber(EFI_SYSTEM_TABLE *SystemTable, UINTN Number) {
    if (!gVerbose) {
        return;
    }
    CHAR16 Buf[24];
    INTN i = 22;
    Buf[23] = 0;
    if (Number == 0) {
        Buf[22] = L'0';
        PrintMessage(SystemTable, &Buf[22]);
        return;
    }
    while (Number > 0 && i >= 0) {
        Buf[i--] = (CHAR16)(L'0' + (Number % 10));
        Number /= 10;
    }
    PrintMessage(SystemTable, &Buf[i + 1]);
}

static VOID PrintHex16(EFI_SYSTEM_TABLE *SystemTable, UINT16 Value) {
    if (!gVerbose) {
        return;
    }
    CHAR16 HexChars[] = L"0123456789ABCDEF";
    CHAR16 Buf[5];
    Buf[0] = HexChars[(Value >> 12) & 0xF];
    Buf[1] = HexChars[(Value >> 8) & 0xF];
    Buf[2] = HexChars[(Value >> 4) & 0xF];
    Buf[3] = HexChars[Value & 0xF];
    Buf[4] = 0;
    PrintMessage(SystemTable, Buf);
}

static BOOLEAN CheckVerboseArgument(EFI_LOADED_IMAGE_PROTOCOL *LoadedImage) {
    if (LoadedImage == NULL || LoadedImage->LoadOptions == NULL || LoadedImage->LoadOptionsSize == 0) {
        return 0;
    }

    // Check as 16-bit Unicode string (standard UEFI / OpenCore)
    UINTN NumChars = LoadedImage->LoadOptionsSize / sizeof(CHAR16);
    CHAR16 *Options16 = (CHAR16 *)LoadedImage->LoadOptions;
    for (UINTN i = 0; i < NumChars; i++) {
        // Match '-v' or 'verbose'
        if (Options16[i] == L'-' && i + 1 < NumChars && (Options16[i + 1] == L'v' || Options16[i + 1] == L'V')) {
            return 1;
        }
        if ((Options16[i] == L'v' || Options16[i] == L'V') &&
            i + 6 < NumChars &&
            (Options16[i + 1] == L'e' || Options16[i + 1] == L'E') &&
            (Options16[i + 2] == L'r' || Options16[i + 2] == L'R') &&
            (Options16[i + 3] == L'b' || Options16[i + 3] == L'B') &&
            (Options16[i + 4] == L'o' || Options16[i + 4] == L'O') &&
            (Options16[i + 5] == L's' || Options16[i + 5] == L'S') &&
            (Options16[i + 6] == L'e' || Options16[i + 6] == L'E')) {
            return 1;
        }
    }

    // Check as 8-bit ASCII string (fallback)
    UINT8 *Options8 = (UINT8 *)LoadedImage->LoadOptions;
    for (UINTN i = 0; i < LoadedImage->LoadOptionsSize; i++) {
        if (Options8[i] == '-' && i + 1 < LoadedImage->LoadOptionsSize && (Options8[i + 1] == 'v' || Options8[i + 1] == 'V')) {
            return 1;
        }
    }

    return 0;
}

EFIAPI
EFI_STATUS
EfiDriverEntryPoint(
    IN EFI_HANDLE           ImageHandle,
    IN EFI_SYSTEM_TABLE     *SystemTable
) {
    EFI_STATUS              Status = EFI_SUCCESS;
    UINTN                   NoHandles = 0;
    EFI_HANDLE              *Handles = NULL;
    UINTN                   Index;
    BOOLEAN                 DeviceFound = 0;

    if (SystemTable == NULL || SystemTable->BootServices == NULL) {
        return EFI_INVALID_PARAMETER;
    }

    // Default: verbose is FALSE (completely silent)
    gVerbose = 0;

    // Check if user passed -v or verbose in config.plist Arguments
    EFI_LOADED_IMAGE_PROTOCOL *LoadedImage = NULL;
    Status = SystemTable->BootServices->HandleProtocol(
        ImageHandle,
        &gEfiLoadedImageProtocolGuid,
        (VOID **)&LoadedImage
    );

    if (!EFI_ERROR(Status) && LoadedImage != NULL) {
        gVerbose = CheckVerboseArgument(LoadedImage);
    }

    PrintMessage(SystemTable, L"[TftBlank] Passive scan for USB IO interfaces...\r\n");

    // Pure passive query for existing EFI_USB_IO_PROTOCOL handles.
    // Zero ConnectController calls, zero touching of storage, PCIe, or memory.
    for (UINTN Attempt = 1; Attempt <= 10; Attempt++) {
        NoHandles = 0;
        Handles = NULL;

        Status = SystemTable->BootServices->LocateHandleBuffer(
            ByProtocol,
            &gEfiUsbIoProtocolGuid,
            NULL,
            &NoHandles,
            &Handles
        );

        if (!EFI_ERROR(Status) && Handles != NULL && NoHandles > 0) {
            break;
        }

        if (Handles != NULL) {
            SystemTable->BootServices->FreePool(Handles);
            Handles = NULL;
        }

        SystemTable->BootServices->Stall(50000); // 50ms
    }

    if (Handles == NULL || NoHandles == 0) {
        PrintMessage(SystemTable, L"[TftBlank] No USB IO protocols found after bus scan.\r\n");
        return EFI_SUCCESS;
    }

    PrintMessage(SystemTable, L"[TftBlank] Found ");
    PrintNumber(SystemTable, NoHandles);
    PrintMessage(SystemTable, L" USB IO device handles. Scanning...\r\n");

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

        PrintMessage(SystemTable, L" [");
        PrintHex16(SystemTable, DevDesc.IdVendor);
        PrintMessage(SystemTable, L":");
        PrintHex16(SystemTable, DevDesc.IdProduct);
        PrintMessage(SystemTable, L"]");

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
                    PrintMessage(SystemTable, L"\r\n[TftBlank] Matched Turing 3.5 display! Sending blanking commands...\r\n");

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
                    if (gVerbose) {
                        SystemTable->BootServices->Stall(300000); // 300ms pause so message is visible in verbose mode
                    }
                    break;
                }
            }
            if (DeviceFound) {
                break;
            }
        }
    }

    SystemTable->BootServices->FreePool(Handles);

    if (!DeviceFound) {
        PrintMessage(SystemTable, L"[TftBlank] Device 1a86:5722 not matched on active interfaces.\r\n");
    }

    return EFI_SUCCESS;
}
