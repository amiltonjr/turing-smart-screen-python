LLVM_PREFIX ?= $(shell if [ -d "/opt/local/libexec/llvm-20/bin" ]; then echo "/opt/local/libexec/llvm-20/bin"; elif [ -d "/opt/local/libexec/llvm-19/bin" ]; then echo "/opt/local/libexec/llvm-19/bin"; elif [ -d "/opt/local/libexec/llvm-18/bin" ]; then echo "/opt/local/libexec/llvm-18/bin"; else echo "/usr/local/bin"; fi)

CC := $(LLVM_PREFIX)/clang
LD := $(LLVM_PREFIX)/lld-link

TARGET := TftBlank.efi
OBJ := TftBlank.o

CFLAGS := -target x86_64-unknown-windows \
          -ffreestanding \
          -fshort-wchar \
          -mno-red-zone \
          -Wall \
          -Wextra \
          -O2 \
          -c

LDFLAGS := -subsystem:efi_boot_service_driver \
           -nodefaultlib \
           -dll \
           -entry:EfiDriverEntryPoint

all: $(TARGET)

$(OBJ): TftBlank.c TftBlank.h
	$(CC) $(CFLAGS) TftBlank.c -o $(OBJ)

$(TARGET): $(OBJ)
	$(LD) $(LDFLAGS) $(OBJ) -out:$(TARGET)
	@rm -f *.lib *.exp

clean:
	rm -f $(OBJ) $(TARGET) *.lib *.exp

.PHONY: all clean
