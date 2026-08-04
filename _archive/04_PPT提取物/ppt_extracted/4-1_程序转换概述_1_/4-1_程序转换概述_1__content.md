# 4-1_程序转换概述_1_

- 幻灯片总数: 86
- 提取时间: 2026-06-15

---

## 第 1 页

程序的转换及机器级表示

陈盛德人工智能与低空技术学院email: shengde-chen@scau.edu.cn

## 第 2 页

程序转换概述

## 第 3 页

回顾：不同层次语言之间的等价转换

每条指令由操 作码和若干地 址码组成

任何高级语言程序最终通过执行若干条指令来完成！

## 第 4 页

回顾：指令和数据

程序启动前，指令和数据都存放在存储器中，形式上没有差别， 都是0/1序列采用”存储程序“工作方式：–	程序由指令组成，程序被启动后，计算机能自动取出一条一条指令执行，在执行过程中无需人的干预。指令执行过程中，指令和数据被从存储器取到CPU，存放在CPU内的寄存器中，指令在IR中，数据在GPR中。

指令中需给出的信息： 操作性质（操作码）源操作数1 或/和 源操作数2

（立即数、寄存器编号、存储地址）

目的操作数地址（寄存器编号、存储地址）

## 第 5 页

机器级指令

机器指令和汇编指令一一对应，都是机器级指令机器指令是一个0/1序列，由若干字段组成

mov [bx+di-6], clIntel格式

或	movb %cl, -6(%bx,%di)AT&T 格式

补码11111010的真值为多少？

R：寄存器内容 M：存储单元内容

操作码	寻址方式	寄存器编号	立即数(位移量)汇编指令是机器指令的符号表示（可有不同格式）长度后缀

指令的功能为：M[R[bx]+R[di]-6]←R[cl]寄存器传送语言 RTL（Register Transfer Language）mov、bx、movb、%bx等都是助记符

## 第 6 页

回顾：高级语言程序转换为机器代码的过程

预处理：在高级语言源程序中插入所有用#include命令指定的文件和用#define声明指定的宏。编译：将预处理后的源程序文件编译生成相应的汇编语言程序。汇编：由汇编程序将汇编语言源程序文件转换为可重定位的机器 语言目标代码文件。链接：由链接器将多个可重定位的机器语言目标文件以及库例程（如printf()库函数）链接起来，生成最终的可执行目标文件。

预处理  (cpp)

编译 (cc1)

汇编  (as)

用GCC编译器套件进行转换的过程printf.o

hello.c源程序  (文本)

hello.i源程序  (文本)

hello.s汇编语 言程序  (文本)

hello.o可重定 位目标 程序(二进制)

链接	hello(ld)	可执行目标程序 (二进制)

## 第 7 页

GCC使用举例

pushl	%ebp

%esp, %ebp$16, %esp  12(%ebp), %eax  8(%ebp), %edx  (%edx, %eax), %eax%eax, -4(%ebp)-4(%ebp), %eax

movl  subl  movl  movl  leal  movl  movl  leave  ret

00000000 <add>:

0:	551:	89 e53:	83 ec 106:	8b 45 0c9:	8b 55 08c:	8d 04 02f:	89 45 fc

12:	8b 45 fc15:	c916:	c3

push	%ebpmov	%esp, %ebp  sub	$0x10, %espmov	0xc(%ebp), %eax  mov	0x8(%ebp), %edxlea	(%edx,%eax,1), %eax  mov	%eax, -0x4(%ebp)  mov	-0x4(%ebp), %eax  leaveret

gcc -E test.c -o test.i

gcc -S test.i -o test.s  gcc –S test.c –o test.s

test.sadd:

位移量

机器指令

汇编指令

编译得到的与反汇编得到的汇编指令形式稍有差异：编译得到的助记符带有长度后缀，数字表现形式是十进制，反汇编的数字表现形式是十六进制

•两个源程序文件main.c和test.c，最终生成可执行文件为test                         gcc -O1 main.c test.c -o test•选项-O1表示一级优化，-O2为二级优化，选项-o指出输出文件名目标文件可用“objdump -d test.o”  反汇编为汇编语言程序

gcc –c test.s –o test.o

## 第 8 页

两种目标文件

“objdump -d test” 结果

00000000 <add>:

0:	551:	89 e53:	83 ec 106:	8b 45 0c9:	8b 55 08c:	8d 04 02f:	89 45 fc

12:	8b 45 fc

15:	c9

16:	c3

push	%ebpmov	%esp, %ebp  sub	$0x10, %espmov	0xc(%ebp), %eax  mov	0x8(%ebp), %edxlea	(%edx,%eax,1), %eax  mov	%eax, -0x4(%ebp)  mov	-0x4(%ebp), %eax  leaveret

test.o中的代码从地址0开始，test中的代码从80483d4开始！

080483d4 <add>:

80483d4:80483d5:80483d7:80483da:80483dd:80483e0:80483e3:80483e6:80483e9:80483ea:

55	push ...89 e5	…83 ec 10	…8b 45 0c	…8b 55 08	…8d 04 02	…89 45 fc	…8b 45 fc	…c9	…c3	ret

“objdump -d test.o”结果

test.o：可重定位目标文件  test：可执行目标文件

## 第 9 页

可执行文件的存储器映像

%esp  (栈顶)

brk

0xC00000000

内核虚存区

共享库区域

堆（heap）(由malloc动态生成)

用户栈（User stack）动态生成

未使用

0x080480000

读写数据段(.data, .bss)

只读代码段(.init, .text, .rodata)

从可 执行 文件 装入

程序(段)头表描述如何映射

ELF 头

程序（段）头表

.data 节.bss 节

.init 节.text 节.rodata 节

.symtab 节.debug 节.line 节.strtab 节

1GB

## 第 10 页

回顾：指令集体系结构（ISA）

ISA指Instruction Set Architecture，即指令集体系结构ISA是一种规约（Specification），它规定了如何使用硬件可执行的指令的集合，包括指令格式、操作种类以及每种操作对应的 操作数的相应规定；指令可以接受的操作数的类型；操作数所能存放的寄存器组的结构，包括每个寄存器的名称、编号、 长度和用途；操作数所能存放的存储空间的大小和编址方式；操作数在存储空间存放时按照大端还是小端方式存放；指令获取操作数的方式，即寻址方式；指令执行过程的控制方式，包括程序计数器、条件码定义等。ISA在计算机系统中是必不可少的一个抽象层，Why？–	没有它，软件无法使用计算机硬件！

–	没有它，一台计算机不能称为“通用计算机”

ISA和计算机组成（Organization，即MicroArchitecture）是何关系？

微体系结构

## 第 11 页

ISA和计算机组成（微结构）之间的关系

不同ISA规定的指令集不同，如，IA-32、MIPS、ARM等

计算机组成必须能够实现ISA规定的功能，如提供GPR、标志、运算电路等 同一种ISA可以有不同的计算机组成，如乘法指令可用ALU或乘法器实现

控制器

输入

设备

输出

设备

PC	MAR

MDR

ALU

标 志 寄 存 器

IR

地址

数据

控制

GPRs

0123

CPU	存储器

01234567

ISA是计算机 组成的抽象

## 第 12 页

IA-32的体系结构是怎样的呢？

设备

输出

设备

MDR

ALU

志 寄 存 器

IR

数据

控制

01

CPU	地址	存储器控制器	PC	MAR	0GPRs	1

234

寄存器个数及各自功能？寄存器宽度？存储空间大小？编址单位？ 指令格式？指令条数？指令操作功能？寻址方式？数据类型？小端/大端？标志寄存器各位含义？PC位数？I/O端口编址方式？……下一节课开始介绍 IA-32 的指令集体系结构（ISA）输入

## 第 13 页

IA-32指令系统概述

支持的数据类型及其格式通用寄存器组织标志寄存器寻址方式指令格式

## 第 14 页

Intel处理器

已停产

现有产品

## 第 15 页

IA-32/x64指令系统概述

x86是Intel开发的一类处理器体系结构的泛称包括 Intel 8086、80286、i386和i486等，因此其架构被 称为“x86”由于数字并不能作为注册商标，因此，后来使用了可注册的 名称，如Pentium、PentiumPro、Core 2、Core i7等现在Intel把32位x86架构的名称x86-32改称为IA-32IA是Intel Architecture的缩写由AMD首先提出了一个兼容IA-32指令集的64位版本扩充了指令及寄存器长度和个数等，更新了参数传送方式AMD称其为AMD64，Intel称其为Intl64命名为“x86-64” ，有时也简称为x64

## 第 16 页

IA-32的体系结构是怎样的呢？

寄存器个数及各自功能？寄存器宽度？存储空间大小？编址单位？ 指令格式？指令条数？指令操作功能？寻址方式？数据类型？小端/大端？标志寄存器各位含义？PC位数？I/O端口编址方式？……

控制器

输入

设备

输出

设备

PC	MAR

MDR

ALU

标 志 寄 存 器

IR

地址

数据

控制

GPRs

01

CPU	存储器

01234

## 第 17 页

控制器

ALU

标 志 寄 存 器

地址

数据

控制

GPRs

01

ffffffff

e5	80483d689	80483d555	80483d4

EIP

bfff0000

MDR

IR

MAR

beeefffc

IA-32的体系结构

8个GPR（0~7），一个EFLAGs，PC为EIP 可寻址空间4GB（编号为0~0xFFFFFFFF）

指令格式变长，操作码变长，指令由若干字段（OP、Mod、SIB等）组成……

## 第 18 页

IA-32支持的数据类型及格式

IA-32架构由16位架构发展而来，因此，虽然字长为32位或更大，但一个字为16位，长度后缀为 w；32位为双字，长度后缀为 l  long double实际长度为80位，但分配96位=12B（按4B对齐）

## 第 19 页

IA-32的寄存器组织

通用寄存器

专用寄存器

段寄存器

## 第 20 页

IA-32的寄存器组织

反映了体系结构发展的轨迹，字长不断扩充，指令保持兼容ST(0) ~ ST(7)是80位，MM0 ~MM7使用其低64位

## 第 21 页

IA-32的标志寄存器

6个条件标志

OF、SF、ZF、CF各是什么标志（条件码）？AF：辅助进位标志（BCD码运算时才有意义）PF：奇偶标志3个控制标志

DF（Direction Flag）：方向标志（自动变址方向是增还是减）IF（Interrupt Flag）：中断允许标志 （仅对外部可屏蔽中断有用）TF（Trap Flag）：陷阱标志（是否是单步跟踪状态）……

8086

80286/386

## 第 22 页

IA-32的寻址方式

寻址方式如何根据指令给定信息得到操作数或操作数地址操作数所在的位置指令中：立即寻址寄存器中：寄存器寻址存储单元中（属于存储器操作数，按字节编址）：其他寻址方式存储器操作数的寻址方式与微处理器的工作模式有关两种工作模式：实地址模式和保护模式实地址模式为与8086/8088兼容而设，加电或复位时寻址空间为1MB，20位地址：(CS)<<4+(IP)保护模式加电后进入，采用虚拟存储管理，多任务情况下隔离、保护80286以上微处理器的工作模式

## 第 23 页

保护模式下的寻址方式

SR段寄存器（间接）确定操作数所在段的段基址有效地址给出操作数在所在段的偏移地址

跳转目标指令地址

当前指令的地址

## 第 24 页

存储器操作数的寻址方式

int x；  float a[100];short b[4][4];  char c;  double d[10];

a[i]的地址如何计算？  104+i×4i=99时，104+99×4=500b[i][ j]的地址如何计算？  504+i×8+j×2i=3、j=2时，504+24+4=532d[i]的地址如何计算？  544+i×8i=9时，544+9×8=616

b31

b0

a[0]

a[99]

b[0][1]

104100

b[0][0]

504500

536532

544

d[0]

d[9]

616

Linux 系 统 ：  double型变量 按4B边界对齐windows系统：  double型变量 按8B边界对齐

## 第 25 页

存储器操作数的寻址方式

b31

b0

a[0]

a[99]

b[0][1]

104100

b[0][0]

504500

536532

544

d[0]

d[9]

616

int x；float a[100];  short b[4][4];  char c;double d[10];各变量应采用什么寻址方式？  x、c：位移 / 基址a[i]：104+i×4，比例变址+位移 d[i]：544+i×8，比例变址+位移  b[i][j]： 504+i×8+j×2，基址+比例变址+位移 将b[i][ j]取到AX中的指令可以是：“movw 504(%ebp,%esi,2), %ax”其中， i×8在EBP中，j在ESI中，  2为比例因子

## 第 26 页

IA-32机器指令格式

位移量和立即数都可以是：1B/2B/4BSIB中基址B和变址I都可是8个GRS中任一个；SS给出比例因子操作码：opcode; W：与机器模式（16 / 32位）一起确定寄存器位数（AL/ AX / EAX）; D：操作方向（确定源和目标）寻址方式（ModRM字节）： mod、r/m、 reg/op三个字段与w字段和机 器模式（16/32）一起确定操作数所在的寄存器编号或有效地址计算方式8d 04 02	leal	(%edx,%eax,1), %eax1000 1101 00 000 100 00 000 010

存储器操作数

## 第 27 页

IA-32中的传送指令

## 第 28 页

IA-32常用指令类型

传送指令通用数据传送指令MOV：一般传送，包括movb、movw和movl等 MOVS：符号扩展传送，如movsbw、movswl等 MOVZ：零扩展传送，如movzwl、movzbl等 XCHG：数据交换PUSH/POP：入栈/出栈，如pushl,pushw,popl,popw等地址传送指令LEA：加载有效地址，如leal (%edx,%eax), %eax”的功能为 R[eax]←R[edx]+R[eax]， 执 行 前 ， 若 R[edx]=i，  R[eax]=j，则指令执行后，R[eax]=i+j输入输出指令IN和OUT：I/O端口与寄存器之间的交换标志传送指令PUSHF、POPF：将EFLAG压栈，或将栈顶内容送EFLAG

## 第 29 页

栈底

新栈顶

栈底

栈顶

“入栈”（pushw %ax）

栈（Stack）是一种采用“先进后出”方式进行访问的一块存 储区，用于嵌套过程调用。从高地址向低地址增长

R[sp]←R[sp]-2、M[R[sp]]←R[ax]

为什么AL在栈顶？

小端方式！

执行前

执行后

## 第 30 页

栈底

新栈顶

栈底

栈顶

“出栈” （popw %ax）

栈（Stack）是一种采用“先进后出”方式进行访问的一块存 储区，用于嵌套过程调用。从高地址向低地址增长

R[ax]←M[R[sp]]、  R[sp]←R[sp]+2

执行前

执行后

原栈顶处的数据送AX

## 第 31 页

程序由指令序列组成

mov	%esp, %ebp

$0x10, %esp  0xc(%ebp), %eax

mov	0x8(%ebp), %edx

80483d4:80483d5:80483d7:80483da:80483dd:80483e0:

5589 e583 ec 10	sub  8b 45 0c	 mov  8b 55 088d 04 02

lea	(%edx,%eax,1), %eax

“objdump -d test” 结果080483d4 <add>:

add函数中有哪些传送指令？  每一条传送指令的功能是什么？

push	%ebp R[esp]←R[esp]-4; M[R[esp]]←R[ebp]

R[ebp]←R[esp]

R[eax]←M[R[ebp]+12]R[edx]←M[R[ebp]+8]

R[eax]←R[edx]+R[eax]  [R[ebp]-4]]←R[eax]R[eax]←M[R[ebp]-4]]

指令的功能用RTL描述

## 第 32 页

程序由指令序列组成

080483d4 <add>:

80483d4:	push	%ebp

100c  0802fc  fc

80483d5:80483d7:80483da:80483dd:80483e0:80483e3:80483e6:80483e9:80483ea:

5589 e583 ec8b 458b 558d 0489 458b 45c9  c3

mov		%esp, %ebp  sub	$0x10, %espmov	0xc(%ebp), %eaxmov	0x8(%ebp), %edxlea	(%edx,%eax,1), %eax  mov	%eax, -0x4(%ebp)  mov	-0x4(%ebp), %eax  leaveret

add函数从80483d4开始！

“objdump -d test” 结果

执行add时，起始EIP=?

EIP←0x80483d4

程序的执行过程如何？ 周而复始执行指令！  指令如何执行？

根据EIP取指令 指令译码取操作数 指令执行 回写结果修改EIP的值

取并 执行 指令

OP

举例

## 第 33 页

指令执行过程

控制器

ALU

标 志 寄 存 器

地址

数据

控制

GPRs

01

bfff0020

80483d680483d580483d4

080483d4 <add>:80483d4:	5580483d5:	89 e5

ESPEIP

bfff0000

80483d4

80483d4

5589e583

Rd

55

7MDR

5589e583

80483d4

IR

5589e583	5589e583

Rd

S1:取指令	S2:指令译码EBP

S3:指令执行

MAR

beeefffc

功能：R[esp]← R[esp]-4，M[R[esp]] ←R[ebp]

bfff0000

push	%ebpmov	%esp, %ebpbfff0020

## 第 34 页

指令执行过程

控制器

ALU

标 志 寄 存 器

地址

数据

控制

GPRs

01

bfff0020

80483d680483d580483d4

080483d4 <add>:80483d4:	5580483d5:	89 e5

push	%ebpmov	%esp, %ebp

ESP

EIP

bfff0020

bfff0000

80483d4

55

7MDR

80483d4

IR

S1:取指令	S2:指令译码 EBP

S3:指令执行

MAR

beeefffc

功能：R[esp]← R[esp]-4，M[R[esp]] ←R[ebp]

54

bfff0000

## 第 35 页

指令执行过程

控制器

ALU

标 志 寄 存 器

地址

数据

控制

GPRs

01

bfff0020

80483d680483d580483d4

080483d4 <add>:80483d4:	5580483d5:	89 e5

push	%ebpmov	%esp, %ebp

ESP

EIP

bfff0020

bfff0000

80483d4

55

7MDR

80483d4

IR

S1:取指令	S2:指令译码 EBP

S3:指令执行

beeefffc

MAR

beeefffc

功能：R[esp]← R[esp]-4，M[R[esp]] ←R[ebp]

54

## 第 36 页

指令执行过程

控制器

ALU

标 志 寄 存 器

地址

数据

控制

GPRs

01

bfff0020

80483d680483d580483d4

080483d4 <add>:80483d4:	5580483d5:	89 e5

push	%ebpmov	%esp, %ebp

ESP

EIP

bfff0020

bfff0000

80483d4

Wr

55

7MDR

WrIR

S1:取指令	S2:指令译码 EBP

S3:指令执行

beeefffc

MAR

beeefffc

bfff0020

bfff0020

beeefffc

功能：R[esp]← R[esp]-4，M[R[esp]] ←R[ebp]

54 beeefffc

## 第 37 页

指令执行过程

控制器

ALU

标 志 寄 存 器

地址

数据

控制

GPRs

01

bfff0020

80483d680483d580483d4

080483d4 <add>:80483d4:	5580483d5:	89 e5

push	%ebpmov	%esp, %ebp

ESP

EIP

bfff0020

bfff0000

Wr

55

7MDR

WrIR

S1:取指令	S2:指令译码EBP

S3:指令执行

beeefffc

MAR

beeefffc

bfff0020

bfff0020

beeefffc

80483d4

功能：R[esp]← R[esp]-4，M[R[esp]] ←R[ebp]

54	beeefffc

## 第 38 页

指令执行过程

控制器

ALU

标 志 寄 存 器

地址

数据

控制

GPRs

01

bfff0020

80483d680483d580483d4

080483d4 <add>:80483d4:	5580483d5:	89 e5

push	%ebpmov	%esp, %ebp

ESP

EIP

bfff0020

bfff0000

80483d5

55

7MDR

S1:取指令	S2:指令译码EBP

S3:指令执行、EIP增量

beeefffc

MAR

beeefffc

bfff0020

bfff0020

beeefffc

开始执行下一条指令

54	beeefffc

Wr

WrIR

## 第 39 页

IA-32中的定点算术运算指令

## 第 40 页

IA-32常用指令类型

定点算术运算指令加 / 减运算（影响标志、不区分无/带符号）  ADD：加，包括addb、addw、addl等       SUB：减，包括subb、subw、subl等增1 / 减1运算      INC：加，包括incb、incw、incl等DEC：减，包括decb、decw、decl等取负运算      NEG：取负，包括negb、negw、negl等比较运算（做减法得到标志、不区分无/带符号）  CMP：比较，包括cmpb、cmpw、cmpl等乘 / 除运算（不影响标志、区分无/带符号）  MUL / IMUL：无符号乘 / 带符号乘DIV/ IDIV：带无符号除 / 带符号除

## 第 41 页

整数乘除指令

乘法指令：可给出一个、两个或三个操作数若给出一个操作数SRC，则另一个源操作数隐含在AL/AX/EAX中，将 SRC和累加器内容相乘，结果存放在AX（16位）或DX-AX（32位）或 EDX-EAX（64位）中。DX-AX表示32位乘积的高、低16位分别在DX  和AX中。 n位× n位=2n位若指令中给出两个操作数DST和SRC，则将DST和SRC相乘，结果在 DST中。n位× n位=n位若指令中给出三个操作数REG、SRC和IMM，则将SRC和立即数IMM  相乘，结果在REG中。n位× n位=n位除法指令：只明显指出除数，用EDX-EAX中内容除以指定的除数若为8位，则16位被除数在AX寄存器中，商送回AL，余数在AH若为16位，则32位被除数在DX-AX寄存器中，商送回AX，余数在DX若为32位，则被除数在EDX-EAX寄存器中，商送EAX，余数在EDX

## 第 42 页

程序由指令序列组成

080483d4 <add>:80483d4:	55

add函数从80483d4开始！

EIP←0x80483d4push	%ebp

若 i= 2147483647，j=2，则执行结果是什么？int main ( ) {int	t1 = 2147483647;int t2 = 2;int	sum = add (t1, t2);

printf(“sum=%d”;sum);

“objdump -d test” 结果

此时，R[eax]=0x2  R[edx]=0x7fffffffadd	%edx，%eax

2147483647=231-1=011∙∙∙1B=0x7fffffff

## 第 43 页

IA-32的寄存器组织

此时，R[eax]=0x2， R[edx]=0x7fffffff即：0号寄存器中为0x2；2号寄存器中为0x7fffffff

## 第 44 页

指令执行过程

控制器

ALU

标 志 寄 存 器

地址

数据

控制

GPRs

bfff0020

e5	80483d689	80483d555	80483d4

ESP

EIP

bfff0000

80483e0

MDR

IR

S1:取指令	S2:指令译码	EBP

S3:指令执行、EIP增量

MAR

7fffffff

beeefffc

20

00

ff

bf

012

8d040289

54

功能：R[eax]← R[edx]+R[eax]*1

## 第 45 页

ALU结构原理

ALU的符号是 什么样的？

ALU

4 Flags

ALUctr猜猜这是什么？

补码加/减器

与门

Flags

或门

右移

非门

AA∧B

A>>1

A∨B

ALUctr

多 路 选 择 器

nn

n R

在 ALU 中 执 行 ：  R[eax]=0x2  R[edx]=0x7fffffff  R[eax]+R[edx]=?

## 第 46 页

回顾：补码加/减器

Sum

加法器

ZF

Cin

Cout

多路选择器

Sub

Bn

OF

补码加/减器

SF

当Sub为1时，做减法 当Sub为0时，做加法

溢出标志

零标志 符号标志

CF=Co⊕Sub进/借位标志

A：0000 0000 0000 0000 0000 0000 0000 0010B：0111 1111 1111 1111 1111 1111 1111 1111sum：1000 0000 0000 0000 0000 0000 0000 0001

## 第 47 页

控制器

ALU

标 志 寄 存 器

地址

数据

控制

GPRs

bfff0020

e5	80483d689	80483d555	80483d4

ESP

EIP

bfff0000

80483e0

MDR

IR

Wr

S1:取指令	S2:指令译码	EBP

S3:指令执行、EIP增量

MAR

beeefffc

20

00

ff

bf

012

8d040289

54

功能：R[eax]← R[edx]+R[eax]*1（执行前）

27fffffff

## 第 48 页

控制器

ALU

标 志 寄 存 器

地址

数据

控制

GPRs

bfff0020

e5	80483d689	80483d555	80483d4

ESP

EIP

bfff0000

80483e0

MDR

IR

Wr

S1:取指令	S2:指令译码	EBP

S3:指令执行、EIP增量

MAR

7fffffff

beeefffc

20

00

ff

bf

12

80000001 0

8d040289

54

功能：R[eax]← R[edx]+R[eax]*1 （执行后）

## 第 49 页

程序执行的结果

int add ( int i, int j ) {  return i+j;}int main ( ) {int t1 = 2147483647;int t2 = 2;int sum = add (t1, t2);  printf(”sum=%d”, sum);}

sum=0x80000001  sum=-2147483647

sum的机器数和 值分别是什么？

两个正数相加结果怎么为负数呢？ 因为计算机是一种模运算系统！高位有效数字被丢失，即发生了溢出

## 第 50 页

定点加法指令举例

假设 R[ax]=FFFAH，R[bx]=FFF0H，则执行以下指令后“addw %bx, %ax”AX、BX中的内容各是什么？标志CF、OF、ZF、SF各是什么？要求分别 将操作数作为无符号数和带符号整数解释并验证指令执行结果。解：功能：R[ax]←R[ax]+R[bx]，指令执行后的结果如下 R[ax]=FFFAH+FFF0H=FFEAH ，BX中内容不变 CF=1，OF=0，ZF=0，SF=1若是无符号整数运算，则CF=1说明结果溢出验证：FFFA的真值为65535-5=65530，FFF0的真值为65515  FFEA的真值为65535-21=65514≠65530+65515，即溢出若是带符号整数运算，则OF=0说明结果没有溢出 验证：FFFA的真值为-6，FFF0的真值为-16FFEA的真值为-22=-6+(-16)，结果正确，无溢出

## 第 51 页

IA-32中的按位运算指令

## 第 52 页

IA-32常用指令类型

（3）按位运算指令– 逻辑运算NOT：非，包括 notb、notw、notl等 AND：与，包括 andb、andw、andl等 OR：或，包括 orb、orw、orl等 XOR：异或，包括 xorb、xorw、xorl等 TEST：做“与”操作测试，仅影响标志仅NOT不影响标志，其他指令执行后OF=CF=0，而ZF和SF则根 据结果设置：若全0，则ZF=1；若最高位为1，则SF=1

## 第 53 页

逻辑运算指令举例

假 设 :  M[0x1000]=00000F89H  M[0x1004]=00001270H  R[eax]=FF000001H  R[ecx]=00001000H

说明以下指令的功能notw %axandl	%eax, (%ecx)  orb 4(%ecx), %al  xorw %ax,4(%ecx)  testl %eax, %ecx

指令执行结果如下：  notw %axR[ax]=not(0001H)=FFFEHandl	%eax, (%ecx)  M[0x1000]=00000F89H∧FF000001H=00000001Horb 4(%ecx), %al  R[al]=01H∨70H=71Hxorw %ax,4(%ecx) M[0x1004]=1270H ⊕ 0001H=1271Htestl %eax, %ecx不改变寄存器和存储单元的内容因为 00001000H∧FF000001H=0故 ZF=0

## 第 54 页

IA-32常用指令类型

（3）按位运算指令– 移位运算（左/右移时，最高/最低位送CF）  SHL/SHR:	逻辑左/右移，包括 shlb、shrw、shrl等SAL/SAR:	算术左/右移，左移判溢出，右移高位补符（移位前、后符号位发生变化，则OF=1 ）  包括 salb、sarw、sarl等ROL/ROR:		循环左/右移，包括 rolb、rorw、roll等 RCL/RCR:	带进位循环左/右移，即：将CF作为操作数一部分循环移位，包括 rclb、rcrw、rcll等

CF

RCL:

## 第 55 页

按位运算指令举例

假设short型变量x被编译器分配在寄存器AX中，R[ax]=FF80H，则以 下汇编代码段执行后变量x的机器数和真值分别是多少？

movw %ax, %dx

salw  addl  sarw

$2, %ax%dx, %ax$1, %ax

1111 1110 0000 0000+1111 1111 1000 00001111 1101 1000 0000>>1=1111 1110 1100 0000

逆向工程：从汇编指令推断出高级语言程序代码

R[dx]←R[ax]1111 1111 1000 0000<<2

算术左移，OF=0

sarw	$1,%ax 可简写成 sarw %ax解：$2和$1分别表示立即数2和1 。x是short型变量，故都是算术移位指令，并进行带符号整数加。 上述代码段执行前R[ax]=x，则执行((x<<2)+x)>>1后，R[ax]=5x/2。算术左移时，AX中的内容在移位前、后符号未发生变化，故OF=0，没有溢出。最终AX的内容为FEC0H，解释为short型整数时，其值为-320。验证：x=-128，5x/2=-320。经验证，结果正确。

## 第 56 页

IA-32中的控制转移指令

## 第 57 页

IA-32常用指令类型

(4) 控制转移指令指令执行可按顺序 或 跳转到转移目标指令处执行无条件转移指令JMP DST：无条件转移到目标指令DST处执行条件转移Jcc DST：cc为条件码，根据标志（条件码）判断是否满足条件，若满足，则转移到目标指令DST处执行，否则按顺序执行条件设置SETcc DST：按条件码cc判断的结果保存到DST（是一个8位寄存器 ）调用和返回指令 （用于过程调用）CALL DST：返回地址RA入栈，转DST处执行 RET：从栈中取出返回地址RA，转到RA处执行

## 第 58 页

IA-32的标志寄存器

6个条件标志OF、SF、ZF、CF各是什么标志（条件码）？AF：辅助进位标志（BCD码运算时才有意义）PF：奇偶标志3个控制标志DF（Direction Flag）：方向标志（自动变址方向是增还是减）IF（Interrupt Flag）：中断允许标志 （仅对外部可屏蔽中断有用）TF（Trap Flag）：陷阱标志（是否是单步跟踪状态）

……

8086

80286/386

## 第 59 页

回顾：整数减法举例

-7- 6 = -7 + (-6) = +3X

-3 - 5 = - 3	+	(- 5)	= - 8√

9 - 6 = 3	√

13 - 5 =	8 √

01

1	011

11

00

0	1

10

1	1	11	1	01	0	1

可利用条件标志进行大小判断

做减法以比较大小，规则：  Unsigned: CF=0时，大于 Signed：OF=SF时，大于

OF=0、ZF=0、 SF=1、借位CF=0

OF=1 、 ZF=0  SF=0、借位CF=0

验证：9>6，故CF=0；13>5，故CF=0 验证：-7<6，故OF≠SF-3<5，故OF≠SF

## 第 60 页

条件转移指令

分三类：根据单 个标志的 值转移按无符 号整数比 较转移按带符 号整数比 较转移

## 第 61 页

例子：程序的机器级表示与执行

sum:….L3:…movl -4(%ebp), %eax  movl 12(%ebp), %edx  subl $1, %edxcmpl		%edx,	%eax  jbe	.L3…第一次循环，执行结果是什么？%eax: 0000 …… 0000%edx: 0000 …… 0000subl 指令的执行结果是什么？  cmpl 指令的执行结果是什么？

int sum(int a[ ], unsigned len){int	i，sum = 0;for (i = 0; i <= len–1; i++)  sum += a[i];return sum;}当参数len为0时，返回值应该是0，但是在机器上执行时，却发生了 存储器访问异常。 Why?i 和 len 分别在哪个寄存器中？  i：%eax；len： %edx

## 第 62 页

subl $1, %edx指令的执行结果

加法器

Ci

Co

多路选择器

Bn

加/减运算部件

ZF  SFSumOFCF=Co ⊕ Sub

当Sub为1时，做减法 Sub

当Sub为0时，做加法

已知EDX中为 len=0000 0000H

“subl $1, %edx”执行时：A=0000 0000H，B为0000 0001H，  Sub=1，因此Sum是32个1，即R[edx]=FFFFFFFFH=0xffffffff完全等价的两种不同写法！

## 第 63 页

cpml %edx,%eax指令的执行结果

“cmpl %edx,%eax”执行时：A=0000 0000H，B为FFFF FFFFH，Sub=1，因此Sum是0…01, CF=1, ZF=0, OF=0, SF=0

加法器

Ci

Co

多路选择器

Bn

加/减运算部件

ZF  SFSumOFCF=Co ⊕ Sub

当Sub为1时，做减法

当Sub为0时，做加法 Sub

已知EDX中为 len-1=FFFF FFFFH

EAX中为 i=0000 0000H

## 第 64 页

jbe .L3指令的执行结果

“cmpl %edx,%eax”执行结果是 CF=1, ZF=0, OF=0, SF=0，  因此，在执行“jbe .L3”时满足条件，应转移到.L3执行！

## 第 65 页

例子：程序的机器级表示与执行

int sum(int a[ ], unsigned len){int	i，sum = 0;for (i = 0; i <= len–1; i++)  sum += a[i];return sum;}当参数len为0时，返回值应该是0，但是在机器上执行时，却发生了 存储器访问异常。 Why?

sum:….L3:…movl -4(%ebp), %eax  movl 12(%ebp), %edx  subl $1, %edxcmpl		%edx,	%eax  jbe	.L3…

“cmpl %edx,%eax”执行结果是 CF=1, ZF=0, OF=0, SF=0，  说明满足条件，应转移到.L3执行！	显然，对于每个 i 都满足条 件，因为任何无符号数都比32个1小，因此循环体被不断执行，  最终导致数组访问越界而发生存储器访问异常。

## 第 66 页

例子：程序的机器级表示与执行

例：int sum(int a[ ], int len){int	i，sum = 0;for (i = 0; i <= len–1; i++)  sum += a[i];return sum;}正确的做法是将参数len声明 为int型。 Why?

sum:….L3:…movl -4(%ebp), %eax  movl 12(%ebp), %edx  subl $1, %edxcmpl		%edx,	%eax  jle	.L3…

“sub $1,%edx”和“cmpl %edx,%eax”执行结果与前面一样！  执行到“jle .L3”指令时，也是 CF=1, ZF=0, OF=0, SF=0！

## 第 67 页

jle .L3指令的执行结果

“cmpl %edx,%eax”执行结果是 CF=1, ZF=0, OF=0, SF=0，  因此，在执行“jle .L3”时不满足条件，应跳出循环执行，使得 执行结果正常。

## 第 68 页

x87浮点处理指令

## 第 69 页

IA-32的浮点处理架构

IA-32的浮点处理架构有两种X87 FPU指令集（gcc默认）SSE指令集（x86-64架构所用）IA-32中处理的浮点数有三种类型float类型：32位 IEEE 754 单精度格式double类型：64位 IEEE 754 双精度格式long double类型：80位双精度扩展格式1位符号位s、15位阶码e（偏置常数为16 383）、1位显式 首位有效位（explicit leading significant bit）j 和 63位 尾数f。它与IEEE 754单精度和双精度浮点格式的一个重要的区别是：它没有隐藏位，有效位数共64位。

## 第 70 页

x87 FPU指令

早期的浮点处理器是作为CPU的外置协处理器出现的x87 FPU 特指与x86处理器配套的浮点协处理器架构浮点寄存器采用栈结构深度为8，宽度为80位，即8个80位寄存器

名称为 ST(0) ~ ST(7)，栈顶为ST(0)，编号分别为 0~7所有浮点运算都按80位扩展精度进行浮点数在浮点寄存器和内存之间传送float、double、long double型变量在内存分别用IEEE 754单精 度、双精度和扩展精度表示，分别占32位（4B）、64位（8B）和 96位（12B，其中高16位无意义）float、double、long double类型变量在浮点寄存器中都用80位扩展精度表示从浮点寄存器到内存：80位扩展精度格式转换为32位或64位从内存到浮点寄存器： 32位或64位格式转换为80位扩展精度格式

## 第 71 页

Intel处理器

已停产BACK现有产品

## 第 72 页

X87 FPU指令

数据传送类装入 （转换为80位扩展精度）FLD：将数据从存储单元装入浮点寄存器栈顶 ST(0)FILD：将数据从int型转换为浮点格式后，装入浮点寄存器栈顶存储（转换为IEEE 754单精度或双精度）FSTx：x为s/l时，将栈顶ST(0)转换为单/双精度格式，然后存 入存储单元FSTPx：弹出栈顶元素，并完成与FSTx相同的功能FISTx：将栈顶数据从int型转换为浮点格式后，存入存储单元  FISTP：弹出栈顶元素，并完成与FISTx相同的功能带P结尾指令表示操作数会出栈，也即ST(1)将变成ST(0)

## 第 73 页

X87 FPU指令

数据传送类交换FXCH：交换栈顶和次栈顶两元素 常数装载到栈顶 FLD1 ：装入常数1.0  FLDZ ：装入常数0.0FLDPI ：装入常数pi (=3.1415926...）FLDL2E ：装入常数log(2)e  FLDL2T ：装入常数log(2)10  FLDLG2 ：装入常数log(10)2  FLDLN2 ：装入常数Log(e)2

## 第 74 页

X87 FPU指令

算术运算类加法FADD/FADDP： 相加／相加后弹出栈FIADD：按int型转换后相加减法FSUB/FSUBP ： 相减／相减后弹出栈 FSUBR/FSUBRP：调换次序相减／相减后弹出栈  FISUB：按int型转换后相减FISUBR：按int型转换并调换次序相减若指令未带操作数，则默认操作数为ST(0）、ST(1） 带R后缀指令是指操作数顺序变反，例如：fsub执行的是x-y，fsubr执行的就是y-x

## 第 75 页

X87 FPU指令

算术运算类乘法FMUL/FMULP: 相乘/相乘后弹出栈 FIMUL：按int型转换后相乘除法FDIV/FDIVP : 相除/相除后弹出栈 FIDIV：按int型转换后相除FDIVR/FDIVRP：调换次序相除／相减后弹出栈  FIDIVR：按int型转换并调换次序相除

## 第 76 页

IA-32浮点操作举例

问题：使用老版本gcc –O2编译时，程序一输出0，程序二输

出是1，是什么原因造成的？

f(10)的值是多少？机器数是多少？

## 第 77 页

IA-32浮点操作举例

8048328:	55

push

%ebp

double f(int x){return 1.0 / x ;}

两条重要指令的功能如下 fld1：将常数1.0压入栈顶ST(0)

fidivl：将指定存储单元操作数M[R[ebp]+8]中的int型数转换为double型，  再将ST(0)除以该数，并将结果存入ST(0)中f(10)=1.0(80 位 扩 展 精 度 )/10( 转 换 为 double)=0.1  0.1=0.00011[0011]B= 0.00011 0011 0011 0011 0011 0011 0011…B

入口参数：int x=10

## 第 78 页

IA-32浮点操作举例

08048334 <main>:

push	%ebpmov		%esp,%ebp  sub	$0x8,%espand	$0xfffffff0,%esp  sub	$0xc,%esp

push	$0xa

5589 e583 ec 0883 e4 f083 ec 0c  6a 0ae8 e1 ff ff ff

call	8048328 <f> //计算a=f(10)

dd 5d f8	fstpl 0xfffffff8(%ebp) //a存入内存

c7 04 24 0a 00 00 00	movl	$0xa,(%esp,1)

call	8048328 <f> //计算b=f(10)

fldl	0xfffffff8(%ebp) //a入栈顶 pop		%eax

fucompp	//比较ST(0)a和ST(1)b

fnstsw %ax	//把FPU状态字送到AX

and	$0x45,%ah  cmp		$0x40,%ah  sete	%al

pop	%edx

e8 d2 ff ff ff  dd 45 f858da e9  df e080 e4 4580 fc 400f 94 c0  5a0f b6 c0

movzbl %al,%eax

50	push	%eax

68 d8 83 04 08	push	$0x80483d8

call	8048268 <_init+0x38>

8048334:8048335:8048337:804833a:804833d:8048340:8048342:8048347:804834a:8048351:8048356:8048359:804835a:804835c:804835e:8048361:8048364:8048367:8048368:804836b:804836c:8048371:8048376:8048377:

e8 f2 fe ff ff  c9c3

leave  ret

…a = f(10) ;b = f(10) ;i = a == b;…

0.1是无限循环小数，无法精确表示，比 较时，a舍入过而b没 有舍入过，故 a≠b

80位→64位

64位→80位

## 第 79 页

IA-32浮点操作举例

8048342:8048347:

e8 e1 ff ff ff  dd 5d f8

call	8048328 <f> //计算afstpl 0xfffffff8(%ebp) //把a存回内存//a产生精度损失

0 00 00	movl	$0xa,(%esp,1)

804834a:8048351:8048356:

c7 04 24 0a 0e8 d2 ff ff ff  dd 5d f0

call	8048328 <f> //计算bfstpl 0xfffffff0(%ebp) //把b存回内存//b产生精度损失

0 00 00		movl	$0xa,(%esp,1)  call	8048328 <f> // 计 算 c  fstp		%st(0)

fldl	0xfffffff8(%ebp) //从内存中载入afldl	0xfffffff0(%ebp) //从内存中载入b

fxch	%st(1)  pop		%eax

8048359:8048360:8048365:8048367:804836a:804836d:804836f:8048370:8048372:

c7 04 24 0a 0e8 c3 ff ff ff  dd d8dd 45 f8dd 45 f0  d9 c958da e9  df e0

fucompp //比较a , b  fnstsw %ax

…a = f(10) ;b = f(10) ;c = f(10) ;i = a == b;

0.1是无限循环小数， 无法精确表示，比较 时，a和b都是舍入过 的，故 a=b！

## 第 80 页

IA-32浮点操作举例

从这个例子可以看出编译器的设计和硬件结构紧密相关。对于编译器设计者来说，只有真正了解底层硬件结构和真正 理解指令集体系结构，才能够翻译出没有错误的目标代码，  并为程序员完全屏蔽掉硬件实现的细节，方便应用程序员开 发出可靠的程序。对于应用程序开发者来说，也只有真正了解底层硬件的结构，才有能力编制出高效的程序，能够快速定位出错的地方，  并对程序的行为作出正确的判断。

## 第 81 页

MMX及SSE指令

## 第 82 页

MMX/SSE指令集的由来

由MMX发展而来的SSE架构MMX指令使用8个64位寄存器MM0~MM7，借用8个80位寄存 器ST(0)~ST(7)中64位尾数所占的位，可同时处理8个字节，或4  个字，或2个双字，或一个64位的数据MMX指令并没带来3D游戏性能的显著提升，故推出SSE指令，  并陆续推出SSE2、SSE3、SSSE3和SSE4等采用SIMD技术的指 令集，这些统称为SSE指令集SSE指令集将80位浮点寄存器扩充到128位多媒体扩展通用寄存 器XMM0~XMM7，可同时处理16个字节，或8个字，或4个双 字（32位整数或单精度浮点数），或两个四字的数据从SSE2开始，还支持128位整数运算，或同时并行处理两个64位 双精度浮点数

## 第 83 页

IA-32中通用寄存器中的编号

反映了体系结构发展的轨迹，字长不断扩充，指令保持兼容ST（0）~ ST（7）是80位，MM0 ~MM7使用其低64位

## 第 84 页

SSE指令（SIMD操作）

080484f0 <dummy_add>:

80484f3:	b9 00 00 00 04	mov	$0x4000000, %ecx80484f8:	b0 01	mov	$0x1, %al  80484fa:		b3 00	mov		$0x0, %bl

用简单的例子来比较普通指令与数据级并行指令的执行速度为使比较结果不受访存操作影响，下例中的运算操作数在寄存器中为使比较结果尽量准确，例中设置的循环次数较大: 0x4000000=226例子只是为了说明指令执行速度的快慢，并没有考虑结果是否溢出以下是普通指令写的程序

循环400 0000H=226次，每次只有一个数（字节）相加

所用时间约为22.643816s

## 第 85 页

SSE指令（SIMD操作）

push	%ebp

mov $0x10049d00, %eax

8048510:	558048511:	b8 00 9d 04 108048516:	89 e58048518:	53

8048519:	bb 20 9d 04 14	mov

mov	%esp, %ebp  push		%ebx$0x14049d20, %ebx  mov	$0x400000, %ecx

804851e:	b9 00 00 40 008048523:	66 0f 6f 008048527:	66 0f 6f 0b

movdqa	(%eax), %xmm0  movdqa	(%ebx), %xmm1

paddb	%xmm0, %xmm1

loop

804852b: 66 0f fc c8  804852f: e2 fa  8048531:	5b8048532:	5d8048533:	c3

804852b <dummy_add_sse+0x1b>  pop	%ebxpop	%ebp  ret

以下是SIMD指令写的程序08048510 <dummy_add_sse>:

循环400000H=222次，每次同时有128/8=16个数（字节）相加

所用时间约为1.411588s22.643816s/

1.411588s= 16.041378,与预期结果一致!  SIMD指令并行 执行效率高!

SIDM指令

## 第 86 页

SSE指令（SIMD操作）

paddb指令（操作数在两个xmm寄存器中）一条指令同时完成16个单字节数据相加类似指令paddw同时完成8个单字数据相加类似指令psubl同时完成4个双字数据相减movdqa指令将双四字（128位）从源操作数处移到目标操作数处用于在 XMM 寄存器与 128 位存储单元之间移入/移出双 四字，或在两个 XMM 寄存器之间移动源操作数或目标操作数是存储器操作数时，操作数必须是 16 字节边界对齐，否则将发生一般保护性异常 (#GP)movdqu指令在未对齐的存储单元中移入/移出双四字

