# Evidências de código — transcrição com linhas originais

Trechos dos snapshots identificados em `source_manifest.json`. Não são patches.

## G: `imu-gateway-firmware-main/imu-gateway-firmware-stm/Core/Src/main.c`

### Linhas 60–111

```c
  60 | #pragma pack(push, 1) // to allocate struct space in memory without initializing all values
  61 | struct _tx_packet {
  62 | 	uint16_t header;
  63 | 	uint8_t counter;
  64 | 	float gyro_x;
  65 | 	float gyro_y;
  66 | 	float gyro_z;
  67 | 	uint16_t acc_x;
  68 | 	uint16_t acc_y;
  69 | 	uint16_t acc_z;
  70 | 	uint16_t acc_tap;
  71 | 	float temp;
  72 | 	float mems_gyro_x;
  73 | 	float mems_gyro_y;
  74 | 	float mems_gyro_z;
  75 | 	float mems_acc_x;
  76 | 	float mems_acc_y;
  77 | 	float mems_acc_z;
  78 | 	uint16_t checksum;
  79 | };
  80 | #pragma pack(pop)
  81 | 
  82 | struct _tx_packet tx_packet;
  83 | volatile uint16_t packet_size = sizeof(tx_packet);
  84 | 
  85 | SCHA63TOutput SCHA63TData; // Variável para armazenar retorno da IMU murata.
  86 | 
  87 | uint16_t checksum;
  88 | 
  89 | float acc_temp; 
  90 | float pcb_ifogx_temp; 
  91 | float pcb_ifogy_temp; 
  92 | float pcb_ifogz_temp; 
  93 | 
  94 | volatile uint8_t package_size = sizeof(tx_packet) - 4; //header:2, checksum:2 
  95 | 
  96 | /// UART buffers
  97 | volatile uint8_t rxBuf[20];
  98 | volatile uint8_t aux_rxBuf[4];
  99 | volatile uint8_t txBuf[70]; // Buffer to send string data.
 100 | 
 101 | // FLAGS
 102 | volatile uint8_t count_datacheck = 0;
 103 | volatile uint8_t count_startbyte = 0;
 104 | volatile uint8_t flag_sent = 1; // Flag that indicates the status of sending. 1 means data sent.
 105 | volatile uint8_t temp_sensor_package_index = 0;
 106 | 
 107 | const uint8_t header = 0xA0;
 108 | const uint8_t gyro_request_char[4] = {0x02, 0x28, 0x2A, 0x03}; // Default to request gyro measurement of rotation {STX, COMMAND(5bits - comm + 3bits - qtdArg), STX+COMMAND, ETX}
 109 | const uint8_t gyro_request_rot_temp[4] = {0x02, 0x30, 0x32, 0x03}; // Default to request gyro rotation and temperature {STX, COMMAND(5bits - comm + 3bits - qtdArg), STX+COMMAND, ETX}
 110 | const uint8_t gyro_reset[4] = {0x02, 0xA0, 0xA2, 0x03}; // Default to reset gyro {STX, COMMAND(5bits - comm + 3bits - qtdArg), STX+COMMAND, ETX}
 111 | const uint8_t sensor_temp_addr[8] = {SENSOR_TEMP_ADDR1, SENSOR_TEMP_ADDR2, SENSOR_TEMP_ADDR3, SENSOR_TEMP_ADDR4, SENSOR_TEMP_ADDR5, SENSOR_TEMP_ADDR6, SENSOR_TEMP_ADDR7, SENSOR_TEMP_ADDR8};
```

### Linhas 136–142

```c
 136 | //Scale factors (pre-calibration)
 137 | const float ifogx_sf = -0.9335;
 138 | const float ifogy_sf = 0.9683;
 139 | const float ifogz_sf = 0.2472;
 140 | const float mems_gyrox_sf = -1.0;
 141 | const float mems_gyroy_sf = 1.0;
 142 | const float mems_gyroz_sf = -1.0;
```

### Linhas 218–261

```c
 218 | 	HAL_TIM_Base_Start_IT(&htim3); // Start the timer interrupt that is set in 100 Hz (to send a sample data)
 219 | 	cSCHA63TInit(GPIOB, GPIO_PIN_14, GPIOB, GPIO_PIN_13, &hspi3); // Inicializa a IMU da Murata
 220 | 	temp_sensors_Init();
 221 | 
 222 | 	tx_packet.counter = 0;
 223 | 	tx_packet.header = 0xA0A0;
 224 | 
 225 | 	gx_requestMode();
 226 | 
 227 | 	/* USER CODE END 2 */
 228 | 
 229 | 	/* Infinite loop */
 230 | 	/* USER CODE BEGIN WHILE */
 231 | 	while (1)
 232 | 	{
 233 | 	if (flag_sent){
 234 | 
 235 | 		// read fiber-optic sensors
 236 | 		clear_uart_buffer(&huart1); // adds 2ms to communication
 237 | 		read_ifog_temp_rate(IFOG_X);
 238 | 
 239 | 		// clear_uart_buffer(&huart1);
 240 | 		read_ifog(IFOG_Y);
 241 | 		
 242 | 		// clear_uart_buffer(&huart1);
 243 | 		read_ifog_temp_rate(IFOG_Z);
 244 | 
 245 | 		clear_uart_buffer(&huart6);
 246 | 		read_acc();
 247 | 		
 248 | 		// read temperature sensors
 249 | 		tx_packet.temp = read_temp(tx_packet.counter - temp_sensor_package_index);
 250 | 		
 251 | 		read_mems();
 252 | 
 253 |     sf_update();
 254 | 
 255 | 		count_datacheck = 0;
 256 | 
 257 | 		// 8 bit counter to monitor communication integrity
 258 | 		tx_packet.counter = (tx_packet.counter + 1) % 256;
 259 | 		temp_sensor_package_index = (tx_packet.counter / 8) * 8;
 260 | 
 261 | 		flag_sent = 0; // wait until data is sent to acquire new data
```

### Linhas 405–425

```c
 405 |   htim3.Instance = TIM3;
 406 |   htim3.Init.Prescaler = 100-1;
 407 |   htim3.Init.CounterMode = TIM_COUNTERMODE_UP;
 408 |   htim3.Init.Period = 10000-1; // 25000 = 40 Hz, 10000 = 100 Hz
 409 |   htim3.Init.ClockDivision = TIM_CLOCKDIVISION_DIV1;
 410 |   htim3.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_DISABLE;
 411 |   if (HAL_TIM_Base_Init(&htim3) != HAL_OK)
 412 |   {
 413 |     Error_Handler();
 414 |   }
 415 |   sClockSourceConfig.ClockSource = TIM_CLOCKSOURCE_INTERNAL;
 416 |   if (HAL_TIM_ConfigClockSource(&htim3, &sClockSourceConfig) != HAL_OK)
 417 |   {
 418 |     Error_Handler();
 419 |   }
 420 |   sMasterConfig.MasterOutputTrigger = TIM_TRGO_RESET;
 421 |   sMasterConfig.MasterSlaveMode = TIM_MASTERSLAVEMODE_DISABLE;
 422 |   if (HAL_TIMEx_MasterConfigSynchronization(&htim3, &sMasterConfig) != HAL_OK)
 423 |   {
 424 |     Error_Handler();
 425 |   }
```

### Linhas 447–454

```c
 447 |   huart1.Instance = USART1;
 448 |   huart1.Init.BaudRate = 115200;
 449 |   huart1.Init.WordLength = UART_WORDLENGTH_8B;
 450 |   huart1.Init.StopBits = UART_STOPBITS_1;
 451 |   huart1.Init.Parity = UART_PARITY_NONE;
 452 |   huart1.Init.Mode = UART_MODE_TX_RX;
 453 |   huart1.Init.HwFlowCtl = UART_HWCONTROL_NONE;
 454 |   huart1.Init.OverSampling = UART_OVERSAMPLING_16;
```

### Linhas 480–487

```c
 480 |   huart2.Instance = USART2;
 481 |   huart2.Init.BaudRate = 921600;//115200;
 482 |   huart2.Init.WordLength = UART_WORDLENGTH_8B;
 483 |   huart2.Init.StopBits = UART_STOPBITS_1;
 484 |   huart2.Init.Parity = UART_PARITY_NONE;
 485 |   huart2.Init.Mode = UART_MODE_TX_RX;
 486 |   huart2.Init.HwFlowCtl = UART_HWCONTROL_NONE;
 487 |   huart2.Init.OverSampling = UART_OVERSAMPLING_16;
```

### Linhas 513–520

```c
 513 |   huart6.Instance = USART6;
 514 |   huart6.Init.BaudRate = 921600;
 515 |   huart6.Init.WordLength = UART_WORDLENGTH_8B;
 516 |   huart6.Init.StopBits = UART_STOPBITS_1;
 517 |   huart6.Init.Parity = UART_PARITY_NONE;
 518 |   huart6.Init.Mode = UART_MODE_TX_RX;
 519 |   huart6.Init.HwFlowCtl = UART_HWCONTROL_NONE;
 520 |   huart6.Init.OverSampling = UART_OVERSAMPLING_16;
```

### Linhas 630–659

```c
 630 | void read_uart_ifog(float *_data){
 631 |  
 632 |   float aux;
 633 |   
 634 |   switch (HAL_UART_Receive(&huart1, rxBuf, 4, 2)){
 635 |     
 636 |     case HAL_OK:
 637 |       memcpy(aux_rxBuf, rxBuf+3, 1);
 638 |       memcpy(aux_rxBuf+1, rxBuf+2, 1);
 639 |       memcpy(aux_rxBuf+2, rxBuf+1, 1);
 640 |       memcpy(aux_rxBuf+3, rxBuf, 1);
 641 |       memcpy(&aux, aux_rxBuf, sizeof(float));
 642 |       // tx_packet.gyro_x = tx_packet.gyro_x*206264.8062471;
 643 |       //*_data = *_data*180.0f*3600.0f/_PI;
 644 |       aux = aux*180.0f*3600.0f/_PI;
 645 |       *_data = aux;
 646 |       break;
 647 | 
 648 |     case HAL_ERROR:
 649 |       *_data = -20.0f; 
 650 |       break;
 651 | 
 652 |     case HAL_BUSY:
 653 |       *_data = 0.0f; 
 654 |       break;
 655 | 
 656 |     case HAL_TIMEOUT:
 657 |       *_data = 20.0f; 
 658 |       break;
 659 |   
```

### Linhas 675–700

```c
 675 | void read_ifog_temp_rate(enum ifogs ifog){
 676 |   
 677 |   switch (ifog){
 678 |     
 679 |     case IFOG_X:
 680 |       gx_requestMode();
 681 |       HAL_UART_Transmit(&huart1, gyro_request_rot_temp, 4, 1);
 682 |       gx_getMode();
 683 |       read_uart_ifog_temp(&pcb_ifogx_temp);
 684 |       read_uart_ifog(&tx_packet.gyro_x);
 685 |     break;
 686 |     
 687 |     case IFOG_Y:
 688 |       gy_requestMode();
 689 |       HAL_UART_Transmit(&huart1, gyro_request_rot_temp, 4, 1);
 690 |       gy_getMode();
 691 |       read_uart_ifog_temp(&pcb_ifogy_temp);
 692 |       read_uart_ifog(&tx_packet.gyro_y);
 693 |     break;
 694 |     
 695 |     case IFOG_Z:
 696 |       gz_requestMode();
 697 |       HAL_UART_Transmit(&huart1, gyro_request_rot_temp, 4, 1);
 698 |       gz_getMode();
 699 |       read_uart_ifog_temp(&pcb_ifogz_temp);
 700 |       read_uart_ifog(&tx_packet.gyro_z);
```

### Linhas 710–741

```c
 710 | void read_uart_ifog_temp(float *_data){
 711 |  
 712 |   uint16_t aux;
 713 |   float aux2;
 714 |   
 715 |   switch (HAL_UART_Receive(&huart1, rxBuf, 2, 5)){
 716 |     
 717 |     case HAL_OK:
 718 |       memcpy(aux_rxBuf, rxBuf+1, 1);
 719 |       memcpy(aux_rxBuf+1, rxBuf, 1);
 720 |       memcpy(&aux, aux_rxBuf, 2);
 721 |       // tx_packet.gyro_x = tx_packet.gyro_x*206264.8062471;
 722 |       //*_data = *_data*180.0f*3600.0f/_PI;
 723 |       if(aux < 8192){
 724 |         aux2 = (aux - 2730.67) / 68.27;
 725 |       }else{
 726 |         aux2 = ((aux % 8192) - 2730.67) / 68.27;
 727 |       }
 728 |       *_data = aux2;
 729 |       break;
 730 | 
 731 |     case HAL_ERROR:
 732 |       *_data = -20.0f; 
 733 |       break;
 734 | 
 735 |     case HAL_BUSY:
 736 |       *_data = 0.0f; 
 737 |       break;
 738 | 
 739 |     case HAL_TIMEOUT:
 740 |       *_data = 20.0f; 
 741 |       break;
```

### Linhas 758–835

```c
 758 | void read_acc(){
 759 | 
 760 |   // 2 attempts to receive accelerometers data. Send a request, get data and check checksum
 761 |   while (count_datacheck < 1){
 762 |   
 763 | 
 764 |     HAL_UART_Transmit(&huart6, gyro_request_char, 4, 2);
 765 | 
 766 |     while (count_startbyte < 5)
 767 |     { // TODO: read all bytes in buffer sent by acc and find header bytes locally, to avoid the use of uart_receive multiple times. This might create an overhead time
 768 |       count_startbyte += 1;
 769 |       HAL_UART_Receive(&huart6, rxBuf, 1, 3);
 770 |       if(rxBuf[0]==0xA0){
 771 |         HAL_UART_Receive(&huart6, rxBuf, 1, 3);
 772 |         if(rxBuf[0]==0xA0){
 773 | 
 774 |           switch (HAL_UART_Receive(&huart6, rxBuf, 14, 4)){
 775 | 
 776 |             case HAL_OK:
 777 |               if(acc_checksum(rxBuf)){
 778 |                 memcpy(&tx_packet.acc_z, rxBuf, 2);
 779 |                 memcpy(&tx_packet.acc_y, rxBuf+2, 2);
 780 |                 memcpy(&tx_packet.acc_x, rxBuf+4, 2);
 781 |                 memcpy(&tx_packet.acc_tap, rxBuf+6, 2);
 782 |                 memcpy(&acc_temp, rxBuf+8, 4);
 783 |                 count_datacheck = 2;
 784 |               }else{
 785 |                 tx_packet.acc_x = CORRUPTED_DATA;
 786 |                 tx_packet.acc_y = CORRUPTED_DATA;
 787 |                 tx_packet.acc_z = CORRUPTED_DATA;
 788 |                 tx_packet.acc_tap = CORRUPTED_DATA;
 789 |                 acc_temp = CORRUPTED_DATA;
 790 |                 count_datacheck += 1;
 791 |               }
 792 |               break;
 793 | 
 794 |             case HAL_TIMEOUT:
 795 |                 tx_packet.acc_x = TIMEOUT;
 796 |                 tx_packet.acc_y = TIMEOUT;
 797 |                 tx_packet.acc_z = TIMEOUT;
 798 |                 tx_packet.acc_tap = TIMEOUT;
 799 |                 acc_temp = TIMEOUT;
 800 |                 count_datacheck += 1;
 801 |               break;
 802 | 
 803 |             default:
 804 |               // For busy and error
 805 |               tx_packet.acc_x = NOT_MODIFIED;
 806 |               tx_packet.acc_y = NOT_MODIFIED;
 807 |               tx_packet.acc_z = NOT_MODIFIED;
 808 |               tx_packet.acc_tap = NOT_MODIFIED;
 809 |               acc_temp = NOT_MODIFIED;
 810 |               count_datacheck += 1;
 811 |           } 
 812 |           
 813 |           // invert signal of accelerometer to indicate x+ 
 814 |           int32_t _aux = (int32_t)tx_packet.acc_x;
 815 |           _aux = (-1)*_aux + 4096; 
 816 |           tx_packet.acc_x = (uint16_t)_aux;
 817 | 
 818 |           count_startbyte = 5;
 819 |         }
 820 |       }
 821 |     }
 822 | 
 823 |     count_startbyte = 0;
 824 |   }
 825 | }
 826 | 
 827 | void clear_uart_buffer(UART_HandleTypeDef *uart_port){
 828 |   int i = 0;
 829 |   while (HAL_UART_Receive(uart_port, rxBuf, 1, 1) == HAL_OK || i>1000){
 830 |     i = i + 1;
 831 |   }
 832 |   for (i=0; i<strlen(rxBuf); i++){
 833 |     rxBuf[i]=0;
 834 |   }
 835 | }
```

### Linhas 923–1046

```c
 923 | uint8_t acc_checksum(uint8_t *_data){
 924 |   uint16_t datasum = 0;
 925 |   uint16_t checksum = 0;
 926 |   for (size_t i = 0; i < 12; i++) {
 927 |     datasum += _data[i];
 928 |   } 
 929 |   memcpy(&checksum, _data+12, 2);
 930 |   if((0xFFFF - datasum)==checksum){
 931 | 	  return 1;
 932 |   }else{
 933 |     return 0;
 934 |   }
 935 | }
 936 | 
 937 | void temp_sensors_Init(void){
 938 |     /**
 939 |    * @brief Configuring the MCP9808
 940 |    * Address the temperature register
 941 |    * if entered directly, should be like this -->> (uint8_t*)0x05
 942 |    */
 943 |   HAL_I2C_Master_Transmit(&hi2c1, SENSOR_TEMP_ADDR1, &addr_temp, 1, 2);
 944 |   HAL_I2C_Master_Transmit(&hi2c1, SENSOR_TEMP_ADDR2, &addr_temp, 1, 2);
 945 |   HAL_I2C_Master_Transmit(&hi2c1, SENSOR_TEMP_ADDR3, &addr_temp, 1, 2);
 946 |   HAL_I2C_Master_Transmit(&hi2c1, SENSOR_TEMP_ADDR4, &addr_temp, 1, 2);
 947 |   HAL_I2C_Master_Transmit(&hi2c1, SENSOR_TEMP_ADDR5, &addr_temp, 1, 2);
 948 | }
 949 | 
 950 | float read_temp(uint8_t index){
 951 |   // TODO: invert T1 with T2, to be 1=x,2=y
 952 | 
 953 |   uint8_t data[2];          // Buffer for reading the register content 
 954 |   uint16_t data_long;       // Variable used to store the whole register content 
 955 |   float temperature;        // Float variable used for storing the temperature value 
 956 |   float temperature_dec;    // Float variable used for calculation of the decimal part 
 957 |   
 958 |   switch(index){
 959 | 
 960 |     case 5:
 961 |       temperature = acc_temp;
 962 |       break;
 963 |       
 964 |     case 6: 
 965 |       temperature = pcb_ifogz_temp;
 966 |       break;
 967 |     
 968 |     case 7: 
 969 |       temperature = pcb_ifogx_temp;
 970 |       break;
 971 | 
 972 |     default:
 973 | 
 974 |     // i2c reboot - when data was lost the i2c connection was breaking
 975 |     if(HAL_I2C_Master_Receive(&hi2c1, sensor_temp_addr[index], data, 2, 2) != HAL_OK){
 976 |       MX_I2C1_Init();
 977 |       temp_sensors_Init();
 978 |     }
 979 |     
 980 |     // calculations from MCP9808 datasheet
 981 |     data_long = ((data[0] << 8u) | data[1]); /* Compose the register content, regardless of the endianess */
 982 |     temperature = ((data_long & 0x0FFF) >> 4); /* Extract the integer part from the fixed point value */
 983 |     temperature_dec = 0.0625; /* Extract decimal part */
 984 |   
 985 |     for(int i=0; i < 4; i++){
 986 |       temperature += ((data_long >> i) & 0x0001) * temperature_dec;
 987 |       temperature_dec *= 2u;
 988 |     }
 989 |   
 990 | 
 991 |   }
 992 | 
 993 |   return temperature; 
 994 | }
 995 | 
 996 | uint16_t calculate_checksum(const uint8_t *data, size_t length) {
 997 |   uint8_t sum1 = 0;
 998 |   uint8_t sum2 = 0;
 999 | 
1000 |   for(size_t i = 0; i < length; i++) {
1001 |     sum1 = (sum1 + data[i]) % 255;
1002 |     sum2 = (sum2 + sum1) % 255;
1003 |   }
1004 | 
1005 |   return (sum2 << 8) | sum1;
1006 | }
1007 | 
1008 | void read_mems(){
1009 |     
1010 |   // read MEMS IMU (Murata)
1011 |     cSCHA63TRead(&SCHA63TData);
1012 |     tx_packet.mems_gyro_x = SCHA63TData.data_gyro[1];
1013 |     tx_packet.mems_gyro_y = SCHA63TData.data_gyro[2];
1014 |     tx_packet.mems_gyro_z = SCHA63TData.data_gyro[0];
1015 |     tx_packet.mems_acc_x = SCHA63TData.data_accl[1];
1016 |     tx_packet.mems_acc_y = SCHA63TData.data_accl[2];
1017 |     tx_packet.mems_acc_z = SCHA63TData.data_accl[0];
1018 | }
1019 | 
1020 | void sf_update(){
1021 | 
1022 |     tx_packet.gyro_x *= ifogx_sf;
1023 |     tx_packet.gyro_y *= ifogy_sf;
1024 |     tx_packet.gyro_z *= ifogz_sf;
1025 |     tx_packet.mems_gyro_x *= mems_gyrox_sf;
1026 |     tx_packet.mems_gyro_y *= mems_gyroy_sf;
1027 |     tx_packet.mems_gyro_z *= mems_gyroz_sf;
1028 | }
1029 | 
1030 | void HAL_TIM_PeriodElapsedCallback(TIM_HandleTypeDef *htim){
1031 | 	if (htim == &htim3){
1032 | 		
1033 | 		// to avoid calculating the checksum before any variable updates
1034 | 		// it was moved to immediately before sending data
1035 | 		tx_packet.checksum = calculate_checksum(
1036 | 			(uint8_t *)&tx_packet + 2,                // Skip header
1037 | 			sizeof(tx_packet) - 2 - 2                  // Exclude header and checksum
1038 |       	);
1039 | 
1040 | 		HAL_UART_Transmit(&huart2, (uint8_t *)&tx_packet, packet_size, 2);
1041 | 
1042 |     	flag_sent = 1;
1043 | 
1044 | 		flag_sent = 1;
1045 | 	}
1046 | }
```

## GM: `imu-gateway-firmware-main/imu-gateway-firmware-stm/Core/Src/stm32f4xx_hal_msp.c`

### Linhas 225–240

```c
 225 | * @retval None
 226 | */
 227 | void HAL_TIM_Base_MspInit(TIM_HandleTypeDef* htim_base)
 228 | {
 229 |   if(htim_base->Instance==TIM3)
 230 |   {
 231 |   /* USER CODE BEGIN TIM3_MspInit 0 */
 232 | 
 233 |   /* USER CODE END TIM3_MspInit 0 */
 234 |     /* Peripheral clock enable */
 235 |     __HAL_RCC_TIM3_CLK_ENABLE();
 236 |     /* TIM3 interrupt Init */
 237 |     HAL_NVIC_SetPriority(TIM3_IRQn, 0, 0);
 238 |     HAL_NVIC_EnableIRQ(TIM3_IRQn);
 239 |   /* USER CODE BEGIN TIM3_MspInit 1 */
 240 | 
```

## GU: `imu-gateway-firmware-main/imu-gateway-firmware-stm/Drivers/STM32F4xx_HAL_Driver/Src/stm32f4xx_hal_uart.c`

### Linhas 1135–1156

```c
1135 | HAL_StatusTypeDef HAL_UART_Transmit(UART_HandleTypeDef *huart, const uint8_t *pData, uint16_t Size, uint32_t Timeout)
1136 | {
1137 |   const uint8_t  *pdata8bits;
1138 |   const uint16_t *pdata16bits;
1139 |   uint32_t tickstart = 0U;
1140 | 
1141 |   /* Check that a Tx process is not already ongoing */
1142 |   if (huart->gState == HAL_UART_STATE_READY)
1143 |   {
1144 |     if ((pData == NULL) || (Size == 0U))
1145 |     {
1146 |       return  HAL_ERROR;
1147 |     }
1148 | 
1149 |     huart->ErrorCode = HAL_UART_ERROR_NONE;
1150 |     huart->gState = HAL_UART_STATE_BUSY_TX;
1151 | 
1152 |     /* Init tickstart for timeout management */
1153 |     tickstart = HAL_GetTick();
1154 | 
1155 |     huart->TxXferSize = Size;
1156 |     huart->TxXferCount = Size;
```

### Linhas 3185–3225

```c
3185 | static HAL_StatusTypeDef UART_WaitOnFlagUntilTimeout(UART_HandleTypeDef *huart, uint32_t Flag, FlagStatus Status,
3186 |                                                      uint32_t Tickstart, uint32_t Timeout)
3187 | {
3188 |   /* Wait until flag is set */
3189 |   while ((__HAL_UART_GET_FLAG(huart, Flag) ? SET : RESET) == Status)
3190 |   {
3191 |     /* Check for the Timeout */
3192 |     if (Timeout != HAL_MAX_DELAY)
3193 |     {
3194 |       if (((HAL_GetTick() - Tickstart) > Timeout) || (Timeout == 0U))
3195 |       {
3196 | 
3197 |         return HAL_TIMEOUT;
3198 |       }
3199 | 
3200 |       if ((READ_BIT(huart->Instance->CR1, USART_CR1_RE) != 0U) && (Flag != UART_FLAG_TXE) && (Flag != UART_FLAG_TC))
3201 |       {
3202 |         if (__HAL_UART_GET_FLAG(huart, UART_FLAG_ORE) == SET)
3203 |         {
3204 |           /* Clear Overrun Error flag*/
3205 |           __HAL_UART_CLEAR_OREFLAG(huart);
3206 | 
3207 |           /* Blocking error : transfer is aborted
3208 |           Set the UART state ready to be able to start again the process,
3209 |           Disable Rx Interrupts if ongoing */
3210 |           UART_EndRxTransfer(huart);
3211 | 
3212 |           huart->ErrorCode = HAL_UART_ERROR_ORE;
3213 | 
3214 |           /* Process Unlocked */
3215 |           __HAL_UNLOCK(huart);
3216 | 
3217 |           return HAL_ERROR;
3218 |         }
3219 |       }
3220 |     }
3221 |   }
3222 |   return HAL_OK;
3223 | }
3224 | 
3225 | /**
```

## M: `imu-gateway-firmware-main/imu-gateway-firmware-stm/Core/Src/SCHA63T.c`

### Linhas 97–151

```c
  97 |   HAL_Delay(25);
  98 | 
  99 |   // set operation mode on
 100 |   write_reg(CS_DUE, REG_MODE, 0);
 101 |   write_reg(CS_UNO, REG_MODE, 0);
 102 |   HAL_Delay(70);
 103 | 
 104 |   // set UNO configuration
 105 |   set_rang_filt(CS_UNO);
 106 | 
 107 |   // reset DUE
 108 |   write_reg(CS_DUE, REG_RESET, 1);
 109 |   HAL_Delay(25);
 110 | 
 111 |   // set DUE operation mode on
 112 |   write_reg(CS_DUE, REG_MODE, 0);
 113 |   write_reg(CS_DUE, REG_MODE, 0);
 114 |   HAL_Delay(1);
 115 | 
 116 |   // set DUE configuration
 117 |   set_rang_filt(CS_DUE);
 118 | 
 119 |   for (int i = 0; i < MAX_TRY_INIT; i++) {
 120 | 	HAL_Delay(525);
 121 | 
 122 | 	// set EOI = 1
 123 | 	write_reg(CS_UNO, REG_RESET, 2);
 124 | 	write_reg(CS_DUE, REG_RESET, 2);
 125 | 
 126 | 	if (test_init_end(CS_UNO) && test_init_end(CS_DUE)) {
 127 | 	  // Enable
 128 | 	  samp_enable = 1;
 129 | 	  return 1;
 130 | 	}
 131 | 
 132 |     write_reg(CS_UNO, REG_RESET, 1); // reset UNO/DUE
 133 |     write_reg(CS_DUE, REG_RESET, 1);
 134 |     HAL_Delay(25);
 135 | 
 136 |     // set operation mode on
 137 | 	write_reg(CS_DUE, REG_MODE, 0);
 138 | 	write_reg(CS_DUE, REG_MODE, 0);
 139 | 	write_reg(CS_UNO, REG_MODE, 0);
 140 | 	HAL_Delay(50);
 141 | 
 142 | 	// set UNO configuration
 143 | 	set_rang_filt(CS_UNO);
 144 | 
 145 |     // set DUE configuration
 146 |     set_rang_filt(CS_DUE);
 147 | 
 148 |     HAL_Delay(45);
 149 |   }
 150 | 
 151 |   return 0;
```

### Linhas 155–185

```c
 155 | void cSCHA63TRead(SCHA63TOutput* SCHA63TData) {
 156 |   static const uint8_t reg1[] = {REG_DUE_RZ, REG_DUE_RY};
 157 |   static const uint8_t reg2[] = {REG_UNO_RX, REG_UNO_AX, REG_UNO_AY, REG_UNO_AZ};
 158 |   uint16_t data1[2], data2[4];
 159 | 
 160 |   //time_ms = (time_ms + 1000 / SAMP_RATE) % 86400000;
 161 | 
 162 |   if (!samp_enable) return;
 163 | 
 164 |   // read sensor registers
 165 |   if (!read_reg(CS_DUE, reg1, 2, data1) || !read_reg(CS_UNO, reg2, 4, data2))  {
 166 |     return;
 167 |   }
 168 |   float gyro[3], accl[3];
 169 |   gyro[0] = (int16_t)data2[0] * SCALE_GYRO * (rang_sel[0] ? 0.5  : 1.0);
 170 |   gyro[1] = (int16_t)data1[1] * SCALE_GYRO * (rang_sel[0] ? 0.5  : 1.0);
 171 |   gyro[2] = (int16_t)data1[0] * SCALE_GYRO * (rang_sel[0] ? 0.5  : 1.0);
 172 |   accl[0] = (int16_t)data2[1] * SCALE_ACCL * (rang_sel[1] ? 0.25 : 1.0) * (ACCL_UNIT ? 9.81 : 1.0);
 173 |   accl[1] = (int16_t)data2[2] * SCALE_ACCL * (rang_sel[1] ? 0.25 : 1.0) * (ACCL_UNIT ? 9.81 : 1.0);
 174 |   accl[2] = (int16_t)data2[3] * SCALE_ACCL * (rang_sel[1] ? 0.25 : 1.0) * (ACCL_UNIT ? 9.81 : 1.0);
 175 | 
 176 |   // cross-axis compensation ([1] 2.6)
 177 |   SCHA63TData->data_gyro[0] = Cx[0][0] * gyro[0] + Cx[0][1] * gyro[1] + Cx[0][2] * gyro[2] - gyrosOffsets[0];
 178 |   SCHA63TData->data_gyro[1] = Cx[1][0] * gyro[0] + Cx[1][1] * gyro[1] + Cx[1][2] * gyro[2] - gyrosOffsets[1];
 179 |   SCHA63TData->data_gyro[2] = Cx[2][0] * gyro[0] + Cx[2][1] * gyro[1] + Cx[2][2] * gyro[2] - gyrosOffsets[2];
 180 |   SCHA63TData->data_accl[0] = Bx[0][0] * accl[0] + Bx[0][1] * accl[1] + Bx[0][2] * accl[2];
 181 |   SCHA63TData->data_accl[1] = Bx[1][0] * accl[0] + Bx[1][1] * accl[1] + Bx[1][2] * accl[2];
 182 |   SCHA63TData->data_accl[2] = Bx[2][0] * accl[0] + Bx[2][1] * accl[1] + Bx[2][2] * accl[2];
 183 |   SCHA63TData->status =  read_stat(&SCHA63TData->temperature);
 184 | 
 185 | }
```

### Linhas 293–389

```c
 293 | uint8_t read_stat(float *temp) {
 294 |   static const uint8_t reg1[] = {REG_TEMP, REG_SUMSTAT};
 295 |   static const uint8_t reg2[] = {REG_TEMP, REG_SUMSTAT};
 296 |   uint16_t data1[2], data2[2];
 297 | 
 298 |   // read status registers
 299 |   if (!read_reg(CS_DUE, reg1, 2, data1) || !read_reg(CS_UNO, reg2, 2, data2)) {
 300 |     return 0xFF; // error
 301 |   }
 302 |   temp[0] = 25.0 + (int16_t)data1[0] * SCALE_TEMP;
 303 |   temp[1] = 25.0 + (int16_t)data2[0] * SCALE_TEMP;
 304 | 
 305 |   // sensor summary status (0x00: all OK)
 306 |   return (uint8_t)(((~data2[1] >> 11) & 0x1) << 5 | // S_OK_Rx_F
 307 |                    ((~data1[1] >> 13) & 0x1) << 4 | // S_OK_Ry_F
 308 |                    ((~data1[1] >> 11) & 0x1) << 3 | // S_OK_Rz_F
 309 |                    ((~data2[1] >>  9) & 0x1) << 2 | // S_OK_Ax_F
 310 |                    ((~data2[1] >>  6) & 0x1) << 1 | // S_OK_Ay_F
 311 |                    ((~data2[1] >>  3) & 0x1) << 0); // S_OK_Az_F
 312 | }
 313 | 
 314 | // read registers of SCHA63T ---------------------------------------------------
 315 | char read_reg(uint8_t cs, const uint8_t *reg, int n, uint16_t *data) {
 316 |   uint8_t req[4] = {0}, rsp[4];
 317 | 
 318 | //  HAL_GPIO_TogglePin(LD1_GPIO_Port, LD1_Pin);
 319 | 
 320 |   for (int i = 0; i <= n; i++) {
 321 |     if (i < n) {
 322 |       req[0] = (reg[i] & 0x1F) << 2; // reg read operation
 323 |       req[3] = crc_spi(req);
 324 |     }
 325 |     write_read_spi(cs, req, rsp);
 326 | 
 327 |     if (i > 0) {
 328 |       if (crc_spi(rsp) != rsp[3]) { // CRC error
 329 |         //trace(2, "read_reg CRC error: cs=%d reg=%02X\r\n", cs, reg[i]);
 330 |         return 0;
 331 |       }
 332 |       data[i-1] = ((uint16_t)rsp[1] << 8) | rsp[2];
 333 |     }
 334 |   }
 335 | 
 336 |   return 1;
 337 | }
 338 | 
 339 | // write register of SCHA63T ---------------------------------------------------
 340 | char write_reg(uint8_t cs, uint8_t reg, uint16_t data) {
 341 |   uint8_t req[4], rsp[4];
 342 | 
 343 |   req[0] = (uint8_t)0x80 | ((reg & 0x1F) << 2); // reg write operation
 344 |   req[1] = (uint8_t)BYTE_H(data);
 345 |   req[2] = (uint8_t)BYTE_L(data);
 346 |   req[3] = crc_spi(req);
 347 |   write_read_spi(cs, req, rsp);
 348 | 
 349 |   req[0] = (reg & 0x1F) << 2; // reg read operation
 350 |   req[1] = req[2] = 0;
 351 |   req[3] = crc_spi(req);
 352 |   write_read_spi(cs, req, rsp);
 353 | 
 354 |   if (crc_spi(rsp) != rsp[3]) {
 355 |     //trace(2, "write_reg CRC error: cs=%d reg=%02X\r\n", cs, reg);
 356 |     return 0;
 357 |   }
 358 |   return 1;
 359 | }
 360 | 
 361 | 
 362 | // write and read 32 bit SPI frame ---------------------------------------------
 363 | void write_read_spi(uint8_t cs, uint8_t *req, uint8_t *rsp) {
 364 | 
 365 |   if(cs == CS_UNO)
 366 |   	  HAL_GPIO_WritePin(SCHA63TGPIOUnoCs_Port, SCHA63TGPIOUnoCs_Pin, GPIO_PIN_RESET);
 367 |     else if(cs == CS_DUE)
 368 |   	  HAL_GPIO_WritePin(SCHA63TGPIODueCs_Port, SCHA63TGPIODueCs_Pin, GPIO_PIN_RESET);
 369 | 
 370 |   HAL_SPI_TransmitReceive(SCHA63TUnoDueSPI, req, rsp, 4, 100);
 371 | 
 372 |   if(cs == CS_UNO)
 373 | 	  HAL_GPIO_WritePin(SCHA63TGPIOUnoCs_Port, SCHA63TGPIOUnoCs_Pin, GPIO_PIN_SET);
 374 |   else if(cs == CS_DUE)
 375 | 	  HAL_GPIO_WritePin(SCHA63TGPIODueCs_Port, SCHA63TGPIODueCs_Pin, GPIO_PIN_SET);
 376 | }
 377 | 
 378 | // SPI frame CRC of SCHA63T ([1] 5.1.6) ----------------------------------------
 379 | uint8_t crc_spi(const uint8_t *data) {
 380 |   uint8_t crc = 0xFF;
 381 | 
 382 |   for (int i = 0; i < 3; i++) {
 383 |     for (int j = 7; j >= 0; j--) {
 384 |       uint8_t bit = crc >> 7;
 385 |       crc <<= 1;
 386 |       if (bit ^ ((data[i] >> j) & 0x01)) crc ^= 0x1D;
 387 |     }
 388 |   }
 389 |   return (uint8_t)~crc;
```

## A: `firmware-ifog-acc-ad24bit-main/Core/Src/main.c`

### Linhas 77–98

```c
  77 | #pragma pack(push, 1)
  78 | typedef struct {
  79 |     uint16_t header;
  80 |     uint16_t counter;
  81 |     float voltages[4];
  82 |     float temperature;
  83 | } TelemetryData;
  84 | #pragma pack(pop)
  85 | 
  86 | TelemetryData packet_data = {//Initializing struct values
  87 | 	.header = 0xA0A0,
  88 |     .counter = 0,
  89 | 	.voltages = {11.1111, 22.2222, 33.3333, 44.4444},
  90 |     .temperature = 55.55
  91 | };
  92 | 
  93 | TelemetryData dma_tx_packet;    // dedicated buffer for DMA
  94 | 
  95 | // flags
  96 | uint8_t flag_timer_main_process = 0;
  97 | uint8_t flag_error_exceeded_timer = 0;	// if I try to activate state 100 Hz and have not yet finished processing data.
  98 | volatile uint8_t flag_uart_dma_busy = 0;
```

### Linhas 137–145

```c
 137 | void send_uart_dma(void) {
 138 |     if(flag_uart_dma_busy==0){
 139 |         flag_uart_dma_busy = 1;
 140 |         memcpy(&dma_tx_packet, &packet_data, sizeof(TelemetryData));
 141 |         if (HAL_UART_Transmit_DMA(&huart1, (uint8_t*)&dma_tx_packet, sizeof(TelemetryData)) != HAL_OK) {
 142 |                 flag_uart_dma_busy = 0; // Reset flag if DMA failed to start
 143 |             }
 144 |         }
 145 | }
```

### Linhas 199–255

```c
 199 |     HAL_TIM_Base_Start_IT(&htim3); 	// 4 Hz   	- read temperature
 200 |     HAL_TIM_Base_Start_IT(&htim4); 	// 100 Hz  	- transmit via uart
 201 |     HAL_TIM_Base_Start_IT(&htim5); 	// 1 MHz  	- microsecond timer
 202 | 
 203 |     /**
 204 |       * timer to generate 10 MHz PWM signal to clock ADS1256
 205 |       * base clk for timer 9 is 100 MHz, so 100MHz/10 = 10MHz, 5/10 = 50% duty cycle
 206 |       */
 207 |     HAL_TIM_PWM_Start(&htim9, TIM_CHANNEL_2);
 208 |     TIM9->CCR2 = 5; // duty cycle = CCR/AAR, for timer9, only CCR2 works.
 209 | 
 210 |     mcp9808_init(); // temperature sensor via i2c
 211 | 
 212 | 	/** Blinking LED to indicate boot*/
 213 | 	for(int i=1; i<6; i++){
 214 | 	  HAL_GPIO_WritePin(GPIOC, GPIO_PIN_13, 0); // ON
 215 | 	  HAL_Delay(100);
 216 | 	  HAL_GPIO_WritePin(GPIOC, GPIO_PIN_13, 1); // OFF
 217 | 	  HAL_Delay(400);
 218 | 	}
 219 | 
 220 |     __HAL_SPI_ENABLE(&hspi1); // must be here since I am using direct SPI access.
 221 |     ads1256_init();
 222 |     HAL_TIM_Base_Start_IT(&htim2); // 1 kHz - read adc, start after ads1256_init because of error flag
 223 | 
 224 |     for(int i = 0; i < 4; i++) {
 225 |         iir_filter_init(&analog_filters[i], IIR_ALPHA);
 226 |     }
 227 |   /* USER CODE END 2 */
 228 | 
 229 |   /* Infinite loop */
 230 |   /* USER CODE BEGIN WHILE */
 231 |   while (1)
 232 |    {
 233 | 
 234 | 	if(flag_timer_main_process == 1){ // state machine - read data and send via uart at 100 Hz
 235 | 		HAL_GPIO_TogglePin(GPIOC, DEBUG_PIN_Pin);
 236 | 
 237 |         // adc_count_value[0] = read_adc_channel(POSITIVE_AIN0);
 238 | 		// adc_count_value[1] = read_adc_channel(POSITIVE_AIN2);
 239 | 		// adc_count_value[2] = read_adc_channel(POSITIVE_AIN4);
 240 | 		// adc_count_value[3] = read_adc_channel(POSITIVE_AIN6);
 241 | 
 242 |         adc_count_value = read_4_adc_channel_optimized();
 243 | 
 244 |         // Convert ADC counts to voltage and apply IIR filter at 1000Hz rate
 245 |         for(int i = 0; i < 4; i++) {
 246 |             adc_voltage[i] = ads1256_count2volt(adc_count_value[i]);
 247 |             if (FILTER_STATE){
 248 |                 packet_data.voltages[i] = iir_filter_update(&analog_filters[i], adc_voltage[i]);
 249 |             } else {
 250 |                 packet_data.voltages[i] = adc_voltage[i];
 251 |             }
 252 |         }
 253 | 
 254 | 
 255 | 		flag_timer_main_process = 0;
```

### Linhas 741–774

```c
 741 | void HAL_UART_TxCpltCallback(UART_HandleTypeDef *huart)
 742 | {
 743 |     if (huart->Instance == USART1) {
 744 |         flag_uart_dma_busy = 0; // DMA transmission complete
 745 |     }
 746 | }
 747 | 
 748 | /**
 749 |  * Use callback function to sent data through uart at a fixed rate of 10 Hz
 750 |  */
 751 | void HAL_TIM_PeriodElapsedCallback(TIM_HandleTypeDef *htim)
 752 | {
 753 | 	if(htim == &htim2){
 754 | 	    // Read ADC data every 1 ms (1000 Hz)
 755 | 		if(flag_timer_main_process == 0){
 756 | 			flag_timer_main_process = 1;
 757 | 			flag_error_exceeded_timer = 0;
 758 | 		}else{
 759 | 			flag_error_exceeded_timer = 1;
 760 |             HAL_GPIO_TogglePin(LED_GPIO_Port, LED_Pin);
 761 | 		}
 762 |         // packet_data.counter++; // counter here indicates lost ADC packages
 763 | 	}
 764 | 
 765 | 	if(htim == &htim3){
 766 |         // Read temperature every 250 ms (4 Hz)
 767 |         packet_data.temperature = read_temperature(SENSOR_TEMP_ADDR1);
 768 | 	}
 769 | 
 770 | 	if(htim == &htim4){
 771 |         // Send packet data via UART every 10 ms (100 Hz)
 772 |         send_uart_dma();
 773 |         packet_data.counter++; // counter here indicates number of packets sent via UART
 774 | 	}
```

## AD: `firmware-ifog-acc-ad24bit-main/Core/Src/ads1256.c`

### Linhas 19–40

```c
  19 | void spi_wrapper_send(uint8_t *command, uint8_t nbytes){
  20 |     SPI_TypeDef *spi = hspi1.Instance;
  21 | 
  22 |     for (uint8_t i = 0; i < nbytes; i++) {
  23 |         while (!(spi->SR & SPI_SR_TXE));    // Wait until TX buffer is empty
  24 |         *(__IO uint8_t *)&spi->DR = command[i]; // Use an 8-bit pointer to DR to force 8-bit access
  25 |         while (!(spi->SR & SPI_SR_RXNE));   // Wait until RX buffer has the shifted-in dummy byte
  26 |         (void)*(__IO uint8_t *)&spi->DR;    // Read to clear RXNE
  27 |     }
  28 |     while (spi->SR & SPI_SR_BSY);   // Wait until SPI is no longer busy before returning
  29 | }
  30 | 
  31 | void spi_wrapper_read(uint8_t *data, uint8_t nbytes){
  32 |     SPI_TypeDef *spi = hspi1.Instance;
  33 | 
  34 |     for (uint8_t i = 0; i < nbytes; i++) {
  35 |         while (!(spi->SR & SPI_SR_TXE));
  36 |         spi->DR = 0xFF;
  37 |         while (!(spi->SR & SPI_SR_RXNE));
  38 |         data[i] = spi->DR;
  39 |     }
  40 |     while (spi->SR & SPI_SR_BSY);
```

### Linhas 146–211

```c
 146 | uint32_t* read_4_adc_channel_optimized(){
 147 | 	uint8_t rx_buf[4][3]= {{0}};
 148 |     static uint32_t output[4] = {0,0,0,0};
 149 |     uint8_t mux_cmd[3];
 150 | 
 151 |     // request to read 1st channel, but do not read memory yet
 152 | 	mux_cmd[0] = CMD_WREG | REG_MUX;
 153 | 	mux_cmd[1] = 0x00;
 154 | 	mux_cmd[2] = POSITIVE_AIN0 | NEGTIVE_AINCOM;
 155 | 	ads1256_wait_drdy();
 156 |     spi_wrapper_send(mux_cmd, 3);
 157 | 	ads1256_sync();
 158 | 	ads1256_wakeup();
 159 | 
 160 |     // request to read 2nd channel and read 1st channel that is already on memory
 161 | 	mux_cmd[2] = POSITIVE_AIN2 | NEGTIVE_AINCOM;
 162 |     ads1256_wait_drdy();
 163 |     spi_wrapper_send(mux_cmd, 3);
 164 | 	ads1256_sync();
 165 | 	ads1256_wakeup();
 166 | 	ads1256_read_data();
 167 |     spi_wrapper_read(rx_buf[0], 3);
 168 | 
 169 |     // request to read 3rd channel and read 2nd channel that is already on memory
 170 |     mux_cmd[2] = POSITIVE_AIN4 | NEGTIVE_AINCOM;
 171 |     ads1256_wait_drdy();
 172 |     spi_wrapper_send(mux_cmd, 3);
 173 |     ads1256_sync();
 174 | 	ads1256_wakeup();
 175 | 	ads1256_read_data();
 176 |     spi_wrapper_read(rx_buf[1], 3);
 177 | 
 178 |     // request to read 4th channel and read 3rd channel that is already on memory
 179 |     mux_cmd[2] = POSITIVE_AIN6 | NEGTIVE_AINCOM;
 180 |     ads1256_wait_drdy();
 181 |     spi_wrapper_send(mux_cmd, 3);
 182 | 	ads1256_sync();
 183 | 	ads1256_wakeup();
 184 | 	ads1256_read_data();
 185 |     spi_wrapper_read(rx_buf[2], 3);
 186 | 
 187 |     // read 4th channel that is already on memory
 188 |     ads1256_wait_drdy();
 189 |     ads1256_read_data();
 190 |     spi_wrapper_read(rx_buf[3], 3);
 191 | 
 192 |     for (int i = 0; i < 4; i++) {
 193 |         output[i] = bytes2counts(rx_buf[i]);
 194 |     }
 195 |     return output;
 196 | }
 197 | 
 198 | 
 199 | /**
 200 |  * @brief Function to check DRDY in while loop instead of interruption.
 201 |  * Interruption causes a delay every time we go to the callback, even
 202 |  * if not doing anything, we loose microseconds.
 203 |  */
 204 | void ads1256_wait_drdy(void){
 205 | 	uint32_t timeout = 0;
 206 | 	while(HAL_GPIO_ReadPin(GPIOA, GPIO_PIN_4) == GPIO_PIN_SET){
 207 | 		timeout++;
 208 | 		if(timeout > 1000000) break;  // timeout after ~1 second
 209 | 		// delay_us(1);
 210 | 	}
 211 | }
```

## FU: `ifog-firmware-main/UARTCommunication.c`

### Linhas 79–148

```c
  79 | unsigned char ProcessUARTByte(unsigned char data)
  80 | {
  81 | 	unsigned char confirmation = OK;
  82 | 
  83 | 	ROM_IntDisable(INT_TIMER0A);
  84 | 
  85 | 	switch ( UARTState )
  86 | 	{
  87 | 		case READ_STX:
  88 | 			if ( data == STX )
  89 | 			{
  90 | 				crc = data;
  91 | 				UARTState = READ_COMMAND;
  92 | 			}
  93 | 			else
  94 | 				confirmation = 0x01;
  95 | 		break;
  96 | 
  97 | 		case READ_COMMAND:
  98 | 			crc += data;
  99 | 			UARTCommand = (enum UARTCommands)(data>>3);
 100 | 			nArg = data & 0x07;
 101 | 			argIndex = 0;
 102 | 			UARTState =(nArg==0)?READ_CRC:READ_ARGS;
 103 | 		break;
 104 | 
 105 | 		case READ_ARGS:
 106 | 			crc += data;
 107 | 			--nArg;
 108 | 			args[ argIndex ] = data;
 109 | 			++argIndex;
 110 | 			if ( nArg == 0 )
 111 | 				UARTState = READ_CRC;
 112 | 		break;
 113 | 
 114 | 		case READ_CRC:
 115 | 			if ( crc != data )
 116 | 			{
 117 | 				confirmation = 0x04;
 118 | 				UARTState = READ_STX;
 119 | 			}
 120 | 			else
 121 | 				UARTState = READ_ETX;
 122 | 		break;
 123 | 
 124 | 		case READ_ETX:
 125 | 			if ( data == ETX )
 126 | 				RunCommand();
 127 | 				//flagRunCommand = 1;
 128 | 			else
 129 | 				confirmation = 0x05;
 130 | 			UARTState = READ_STX;
 131 | 		break;
 132 | 	}
 133 | 
 134 | 	if (confirmation!=OK)
 135 | 	{
 136 | 		// Set the communication error flag
 137 | 		//statusFlag = SATATUS_COMM_ERR;
 138 | 
 139 | 		// Put the dir pin in the RS486 transceive in sending mode
 140 | 		ROM_GPIOPinWrite(DIRPORT, DIRPIN, DIRPIN);
 141 | 		ROM_UARTCharPutNonBlocking(UART0_BASE, confirmation);
 142 | 		ROM_UARTCharPutNonBlocking(UART0_BASE, data);
 143 | 	}
 144 | 
 145 | 
 146 | 	return ( confirmation );
 147 | 
 148 | }
```

### Linhas 189–275

```c
 189 | 		case GET_TEMP:
 190 | 			u_f_aux.f = temperature;
 191 | 			ROM_UARTCharPut(UART0_BASE, u_f_aux.ui8[3]);
 192 | 			ROM_UARTCharPut(UART0_BASE, u_f_aux.ui8[2]);
 193 | 			ROM_UARTCharPut(UART0_BASE, u_f_aux.ui8[1]);
 194 | 			ROM_UARTCharPut(UART0_BASE, u_f_aux.ui8[0]);
 195 | 		break;
 196 | 
 197 | 		case SET_RAMP:
 198 | 			u_f_aux.ui8[0] = args[3];
 199 | 			u_f_aux.ui8[1] = args[2];
 200 | 			u_f_aux.ui8[2] = args[1];
 201 | 			u_f_aux.ui8[3] = args[0];
 202 | 			rampRad = u_f_aux.f;
 203 | 		break;
 204 | 
 205 | 		case GET_ROTATION:
 206 | 			// Send temperature
 207 | 			u_f_aux.f = filteredRampRad;
 208 | 			ROM_UARTCharPutNonBlocking(UART0_BASE, u_f_aux.ui8[3]);
 209 | 			ROM_UARTCharPutNonBlocking(UART0_BASE, u_f_aux.ui8[2]);
 210 | 			ROM_UARTCharPutNonBlocking(UART0_BASE, u_f_aux.ui8[1]);
 211 | 			ROM_UARTCharPutNonBlocking(UART0_BASE, u_f_aux.ui8[0]);
 212 | 		break;
 213 | 
 214 | 		case GET_ROTATION_TEMP:
 215 | 			// Send temperature
 216 | 			if(statusFlag)
 217 | 				u_ui16_aux.ui16 = (unsigned short int) (8191 + statusFlag);
 218 | 			else
 219 | 				u_ui16_aux.ui16 = (unsigned short int)(temperature * 68.26666667 + 2730.666667);
 220 | 			ROM_UARTCharPutNonBlocking(UART0_BASE, u_ui16_aux.ui8[1]);
 221 | 			ROM_UARTCharPutNonBlocking(UART0_BASE, u_ui16_aux.ui8[0]);
 222 | 
 223 | 			// Send rotation
 224 | 			u_f_aux.f = filteredRampRad;
 225 | 			ROM_UARTCharPutNonBlocking(UART0_BASE, u_f_aux.ui8[3]);
 226 | 			ROM_UARTCharPutNonBlocking(UART0_BASE, u_f_aux.ui8[2]);
 227 | 			ROM_UARTCharPutNonBlocking(UART0_BASE, u_f_aux.ui8[1]);
 228 | 			ROM_UARTCharPutNonBlocking(UART0_BASE, u_f_aux.ui8[0]);
 229 | break;
 230 | 
 231 | 		case GET_ANGLE:
 232 | 			u_i32_aux.i32 = (int) (angle * 8388608 / _2PI);
 233 | 			ROM_UARTCharPutNonBlocking(UART0_BASE, u_i32_aux.ui8[2]);
 234 | 			ROM_UARTCharPutNonBlocking(UART0_BASE, u_i32_aux.ui8[1]);
 235 | 			ROM_UARTCharPutNonBlocking(UART0_BASE, u_i32_aux.ui8[0]);
 236 | 		break;
 237 | 
 238 | 		case GET_ANGLE_TEMP:
 239 | 			// Send temperature
 240 | 			if(statusFlag)
 241 | 				u_ui16_aux.ui16 = (unsigned short int) (8191 + statusFlag);
 242 | 			else
 243 | 				u_ui16_aux.ui16 = (unsigned short int)(temperature * 68.26666667 + 2730.666667);
 244 | 			ROM_UARTCharPutNonBlocking(UART0_BASE, u_ui16_aux.ui8[1]);
 245 | 			ROM_UARTCharPutNonBlocking(UART0_BASE, u_ui16_aux.ui8[0]);
 246 | 
 247 | 			// Send angle
 248 | 			u_i32_aux.i32 = (int) (angle * 8388608 / _2PI);
 249 | 			ROM_UARTCharPutNonBlocking(UART0_BASE, u_i32_aux.ui8[2]);
 250 | 			ROM_UARTCharPutNonBlocking(UART0_BASE, u_i32_aux.ui8[1]);
 251 | 			ROM_UARTCharPutNonBlocking(UART0_BASE, u_i32_aux.ui8[0]);
 252 | 		break;
 253 | 
 254 | 		case GET_ROTATION_ANGLE_TEMP:
 255 | 			// Send temperature
 256 | 			if(statusFlag)
 257 | 				u_ui16_aux.ui16 = (unsigned short int) (8191 + statusFlag);
 258 | 			else
 259 | 				u_ui16_aux.ui16 = (unsigned short int)(temperature * 68.26666667 + 2730.666667);
 260 | 			ROM_UARTCharPutNonBlocking(UART0_BASE, u_ui16_aux.ui8[1]);
 261 | 			ROM_UARTCharPutNonBlocking(UART0_BASE, u_ui16_aux.ui8[0]);
 262 | 
 263 | 			// Send angle
 264 | 			u_i32_aux.i32 = (int) (angle * 8388608 / _2PI);
 265 | 			ROM_UARTCharPutNonBlocking(UART0_BASE, u_i32_aux.ui8[2]);
 266 | 			ROM_UARTCharPutNonBlocking(UART0_BASE, u_i32_aux.ui8[1]);
 267 | 			ROM_UARTCharPutNonBlocking(UART0_BASE, u_i32_aux.ui8[0]);
 268 | 
 269 | 			// Send rotation
 270 | 			u_f_aux.f = filteredRampRad;
 271 | 			ROM_UARTCharPutNonBlocking(UART0_BASE, u_f_aux.ui8[3]);
 272 | 			ROM_UARTCharPutNonBlocking(UART0_BASE, u_f_aux.ui8[2]);
 273 | 			ROM_UARTCharPutNonBlocking(UART0_BASE, u_f_aux.ui8[1]);
 274 | 			ROM_UARTCharPutNonBlocking(UART0_BASE, u_f_aux.ui8[0]);
 275 | 		break;
```

## F: `ifog-firmware-main/main.c`

### Linhas 69–97

```c
  69 | volatile float 			temperature;
  70 | /**
  71 |  * Stores the sending timer period to guarantee 100 Hz transmission rate
  72 |  */
  73 | volatile float 			timerPeriod = 1e-2;
  74 | // Stores witch variables must be sent
  75 | volatile unsigned char 	sendParameters = SEND_ROTATION | SEND_ANGLE | SEND_TEMPERATURE;
  76 | // Stores if the gyroscpope is operating in closed loop mode or open loop mode
  77 | volatile unsigned char 	closedLoop = ON;
  78 | // Flag to inform if the UART is being used to send data
  79 | volatile unsigned char 	UARTTXBusyFlag = 0;
  80 | // Error flag: OK = 0
  81 | volatile unsigned char 	statusFlag = SATATUS_OK;
  82 | volatile unsigned char 	gFlag = 0;
  83 | 
  84 | // Gyro parameters
  85 | volatile float 			scaleFactor = SCALE_FACTOR; // seconds
  86 | // volatile float 			scaleFactor = 5.5155; // seconds
  87 | volatile float			propagationTime = TRANSIT_TIME; // tau
  88 | /* Time constant used to integrate the angular velocity (2*76*tau) */
  89 | volatile float			ADCPeriod = NUMBEROFPHASES*SAGNACNUMSAMPLES*TRANSIT_TIME;
  90 | /* Instantaneous angular velocity [rad/s] sent as output data */
  91 | volatile float 			filteredRampRad = 0;
  92 | /* Simple Euler integration of the angular velocity sent as output data */
  93 | volatile float 			angle = 0;
  94 | // Communication error flag
  95 | volatile unsigned char  commErrFlag = 0;
  96 | // Initialization flag. GO = 1
  97 | volatile unsigned char  initFlag = 1;
```

### Linhas 261–283

```c
 261 | 							ramp = -_2PI/countsToRad;
 262 | 
 263 | 					twoPiDeviation += twoPiPercent/200;
 264 | 
 265 | 					// Low pass filtering
 266 | 					filteredRampRad = convolutionIFIR(ramp) * countsToRad / scaleFactor *1.07;
 267 | 					//filteredRampRad = rampRad;
 268 | 
 269 | 					// Integrates the rotation
 270 | 					angle += (filteredRampRad  * ADCPeriod) / scaleFactor;
 271 | 				}
 272 | 				// Open-loop operation
 273 | 				else
 274 | 				{
 275 | 					/** To apply ramp in the open loop */
 276 | 					ramp = 0/countsToRad;
 277 | 
 278 | 					// Low pass filtering
 279 | 					filteredRampRad = convolutionIFIR(ramp) * countsToRad / scaleFactor *1.07;
 280 | 					//filteredRampRad = rampRad;
 281 | 
 282 | 					// Integrates the rotation
 283 | 					angle += (filteredRampRad  * ADCPeriod) / scaleFactor;
```

### Linhas 401–439

```c
 401 | 	// DIR AMD2483 (RS485 transceiver)
 402 | 	ROM_SysCtlPeripheralEnable(DIRENABLE);
 403 | 	ROM_GPIOPinTypeGPIOOutput(DIRPORT, DIRPIN);
 404 | 	ROM_GPIOPinWrite(DIRPORT, DIRPIN, 0); // Sets as input
 405 | 
 406 | 	// Enable ADS1672 DRDY interrupt.
 407 | 	ROM_IntEnable(ADS1672DRDYINTPORT);
 408 | 	// Enable the UART interrupt.
 409 | 	ROM_IntEnable(INT_UART0);
 410 | 
 411 | 	// Set interrupt priorities.
 412 | 	// The hardware priority mechanism only looks at the upper 3 bits of the priority level
 413 | 	// Smaller numbers correspond to higher interrupt priorities; priority 0 is the highest
 414 | 	// interrupt priority
 415 | 	// Set ADS1672 DRDY interrupt with highest priority.
 416 | 	ROM_IntPrioritySet(ADS1672DRDYINTPORT, 	0b00100000);
 417 | 	// Set UART with medium priority.
 418 | 	ROM_IntPrioritySet(INT_UART0, 			0b01000000);
 419 | 	// Set timer with low priority.
 420 | 	ROM_IntPrioritySet(INT_TIMER0A, 		0b10000000);
 421 | 
 422 | 	// Setting the interrupts type
 423 | 	// ADS1672DRDY (PB3)
 424 | 	ROM_GPIOIntTypeSet(ADS1672DRDYPORT, ADS1672DRDYPIN, GPIO_RISING_EDGE);
 425 | 
 426 | 	// Set ADS1672 DRDY interrupt pin
 427 | 	GPIOIntEnable(ADS1672DRDYPORT, ADS1672DRDYINTPIN);
 428 | 
 429 | 	// Trimming to sync modulation sync signal and phases
 430 | 	ROM_SysCtlDelay(CYCLES(74*5.76e-6));
 431 | 
 432 | 	// Enable all interrupts
 433 | 	ROM_IntMasterEnable();
 434 | 
 435 | 	// TimerSet(timerPeriod);
 436 | 
 437 | 	// ROM_TimerEnable(TIMER0_BASE, TIMER_A);
 438 | 	// // Enable timer interrupt
 439 | 	// ROM_IntEnable(INT_TIMER0A);
```

### Linhas 709–794

```c
 709 | void IntUARTHandler(void)
 710 | {
 711 | 	uint32_t ui32Status;
 712 | 
 713 | 	// Get the interrrupt status.
 714 | 	//ui32Status = ROM_UARTIntStatus(UART0_BASE, true);
 715 | 	ui32Status = HWREG(UART0_BASE + UART_O_MIS);
 716 | 
 717 | 	// Clear the interrupt flags
 718 | 	//ROM_UARTIntClear(UART0_BASE, ui32Status);
 719 | 	HWREG(UART0_BASE + UART_O_ICR) = ui32Status;
 720 | 
 721 | 	// If the transmit buffer is empt set the uart to receive bits
 722 | 	// Put the dir pin in the RS486 transceive in receive mode
 723 | 	if((ui32Status & UART_INT_TX) && !UARTTXBusyFlag)
 724 | 		ROM_GPIOPinWrite(DIRPORT, DIRPIN, 0);
 725 | 
 726 | 	// Precess the arrived byte
 727 | 	while(ROM_UARTCharsAvail(UART0_BASE))
 728 | 		commErrFlag = ProcessUARTByte((unsigned char)ROM_UARTCharGetNonBlocking(UART0_BASE));
 729 | }
 730 | 
 731 | //*****************************************************************************
 732 | // Sends the rotation value
 733 | //*****************************************************************************
 734 | void IntTimer0AHandler(void)
 735 | {
 736 | 	union_i32	u_i32_aux;
 737 | 	union_ui16	u_ui16_aux;
 738 | 	union_f		u_f_aux;
 739 | 
 740 | 	// Clear TIMER 0A interrupt flag
 741 | 	ROM_TimerIntClear(TIMER0_BASE, TIMER_TIMA_TIMEOUT);
 742 | 	ROM_IntPendClear(INT_TIMER0A);
 743 | 
 744 | 	// Set UART in sending mode
 745 | 	UARTTXBusyFlag = 1;
 746 | 
 747 | 	// Put the dir pin in the RS486 transceive in sending mode
 748 | 	ROM_GPIOPinWrite(DIRPORT, DIRPIN, DIRPIN);
 749 | 
 750 | 	if(statusFlag)
 751 | 	{
 752 | 		if(++contStatusFlag > contStatusFlagMax )
 753 | 		{
 754 | 			contStatusFlag = 0;
 755 | 			statusFlag = 0;
 756 | 		}
 757 | 	}
 758 | 
 759 | 
 760 | 	// Send temperature
 761 | 	if(sendParameters & SEND_TEMPERATURE)
 762 | 	{
 763 | 		if(statusFlag)
 764 | 			u_ui16_aux.ui16 = (unsigned short int) (temperature * 68.26666667 + 2730.666667) + (statusFlag<<13);
 765 | 		else
 766 | 			u_ui16_aux.ui16 = (unsigned short int) (temperature * 68.26666667 + 2730.666667);
 767 | 
 768 | 		ROM_UARTCharPutNonBlocking(UART0_BASE, u_ui16_aux.ui8[1]);
 769 | 		ROM_UARTCharPutNonBlocking(UART0_BASE, u_ui16_aux.ui8[0]);
 770 | 	}
 771 | 
 772 | 	// Send angle
 773 | 	if(sendParameters & SEND_ANGLE)
 774 | 	{
 775 | 		//u_i32_aux.i32 = (int) (angle * 8388608 / _2PI);
 776 | 		u_i32_aux.i32 = (int) (3 * 8388608 / _2PI);
 777 | 		ROM_UARTCharPutNonBlocking(UART0_BASE, u_i32_aux.ui8[2]);
 778 | 		ROM_UARTCharPutNonBlocking(UART0_BASE, u_i32_aux.ui8[1]);
 779 | 		ROM_UARTCharPutNonBlocking(UART0_BASE, u_i32_aux.ui8[0]);
 780 | 	}
 781 | 
 782 | 	// Send rotation
 783 | 	if(sendParameters & SEND_ROTATION)
 784 | 	{
 785 | 		u_f_aux.f = filteredRampRad;
 786 | 		ROM_UARTCharPutNonBlocking(UART0_BASE, u_f_aux.ui8[3]);
 787 | 		ROM_UARTCharPutNonBlocking(UART0_BASE, u_f_aux.ui8[2]);
 788 | 		ROM_UARTCharPutNonBlocking(UART0_BASE, u_f_aux.ui8[1]);
 789 | 		ROM_UARTCharPutNonBlocking(UART0_BASE, u_f_aux.ui8[0]);
 790 | 	}
 791 | 
 792 | 	// Let UART free for receiving
 793 | 	UARTTXBusyFlag = 0;
 794 | }
```

## AT: `firmware-ifog-acc-ad24bit-main/Core/Src/mcp9808.c`

### Linhas 1–46

```c
   1 | #include "mcp9808.h"
   2 | 
   3 | extern I2C_HandleTypeDef hi2c1;
   4 | static uint8_t is_initialized = 0;
   5 | 
   6 | float read_temperature(uint16_t slave_addr) {
   7 |     uint8_t data[2] = {0, 0};
   8 |     uint16_t data_long;
   9 |     float temperature;
  10 |     float temperature_dec;
  11 | 
  12 |     if (HAL_I2C_Master_Receive(&hi2c1, slave_addr, data, 2, 10) != HAL_OK) {
  13 |         mcp9808_init();
  14 |         return -99.99;
  15 |     }
  16 | 
  17 |     data_long = ((data[0] << 8u) | data[1]);
  18 |     temperature = ((data_long & 0x0FFF) >> 4);
  19 |     temperature_dec = 0.0625;
  20 | 
  21 |     for(int i = 0; i < 4; i++) {
  22 |         temperature += ((data_long >> i) & 0x0001) * temperature_dec;
  23 |         temperature_dec *= 2u;
  24 |     }
  25 | 
  26 |     // negative temperatures
  27 |     if ((data[0] & 0x10) == 0x10) {
  28 |         temperature -= 256.0;
  29 |     }
  30 | 
  31 |     return temperature;
  32 | }
  33 | 
  34 | void mcp9808_init() {
  35 |     uint8_t temp_reg_pointer = TEMP_REG_ADDR;
  36 | 
  37 |     // Transmit just the register address to set the pointer
  38 |     if (HAL_I2C_Master_Transmit(&hi2c1, SENSOR_TEMP_ADDR1, &temp_reg_pointer, 1, 100) != HAL_OK) {
  39 |         HAL_I2C_Master_Transmit(&hi2c1, SENSOR_TEMP_ADDR1, &temp_reg_pointer, 1, 100);
  40 |     }
  41 | 
  42 |     // Optionally set resolution
  43 |     // uint8_t res_data[2] = {RES_REG_ADDR, RESOLUTION_05000};
  44 |     // HAL_I2C_Master_Transmit(&hi2c1, SENSOR_TEMP_ADDR1, res_data, 2, 100);
  45 | 
  46 |     is_initialized = 1;
```
