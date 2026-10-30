/* Reference extracted verbatim from supplied gateway main.c lines 60-80 and 996-1006.
 * Snapshot 7e0b963b646d343559ff8ee0116c4e270f39bdaa. No target firmware modified.
 * Host-only ABI oracle, not execution of STM32 acquisition or HAL.
 */
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#pragma pack(push, 1) // to allocate struct space in memory without initializing all values
struct _tx_packet {
	uint16_t header;
	uint8_t counter;
	float gyro_x;
	float gyro_y;
	float gyro_z;
	uint16_t acc_x;
	uint16_t acc_y;
	uint16_t acc_z;
	uint16_t acc_tap;
	float temp;
	float mems_gyro_x;
	float mems_gyro_y;
	float mems_gyro_z;
	float mems_acc_x;
	float mems_acc_y;
	float mems_acc_z;
	uint16_t checksum;
};
#pragma pack(pop)
uint16_t calculate_checksum(const uint8_t *data, size_t length) {
  uint8_t sum1 = 0;
  uint8_t sum2 = 0;

  for(size_t i = 0; i < length; i++) {
    sum1 = (sum1 + data[i]) % 255;
    sum2 = (sum2 + sum1) % 255;
  }

  return (sum2 << 8) | sum1;
}
_Static_assert(sizeof(struct _tx_packet) == 53, "wire size");
_Static_assert(offsetof(struct _tx_packet, checksum) == 51, "checksum offset");
_Static_assert(offsetof(struct _tx_packet, temp) == 23, "temperature offset");
int main(void) {
    const uint16_t little = 1;
    if (*(const uint8_t*)&little != 1 || sizeof(float) != 4) return 2;
    struct _tx_packet p = {
        .header=0xA0A0, .counter=0x5A, .gyro_x=1.0f, .gyro_y=-2.0f, .gyro_z=0.5f,
        .acc_x=0x1234, .acc_y=0x5678, .acc_z=0x9ABC, .acc_tap=0xDEF0,
        .temp=25.25f, .mems_gyro_x=0.25f, .mems_gyro_y=-0.125f, .mems_gyro_z=16.0f,
        .mems_acc_x=1.5f, .mems_acc_y=-9.81f, .mems_acc_z=27.125f
    };
    p.checksum = calculate_checksum((const uint8_t*)&p + 2, sizeof(p)-4);
    return fwrite(&p, 1, sizeof(p), stdout) == sizeof(p) ? 0 : 1;
}
