# 5_程序的链接_1_

- 幻灯片总数: 99
- 提取时间: 2026-06-15

---

## 第 1 页

程序的链接

陈盛德人工智能与低空技术学院email: shengde-chen@scau.edu.cn

## 第 2 页

可执行文件生成概述

## 第 3 页

一个典型程序的转换处理过程

#include <stdio.h>int main(){printf("hello, world\n");}

经典的“ hello.c ”C-源程序

35 105 110 99 108 117 100 101 32 60 115 116 100 105 111 46

h	>	\ n	\ n	i	n	t	< s p >	m	a	i	n	(	)	\ n	{  104 62 10 10 105 110 116 32 109 97 105 110 40 41 10 123\ n	< sp>	< sp>	< sp>	< sp>	p	r	i	n	t	f	(	"	h	e	l  10 32 32 32 32 112 114 105 110 116 102 40 34 104 101 108l	o	,	< s p >	w	o	r	l	d	\	n	"	)	;	\ n	}  108 111 44 32 119 111 114 108 100 92 110 34 41 59 10 125

hello.c的ASCII文本表示#	i	n	c	l	u	d	e	< s p >	<	s	t	d	i	o	.

功能：输出“hello,world”

预处理  (cpp)

编译 (cc1)

汇编  (as)

printf.o

计算机不能直接执行hello.c！

hello.c源程序  (文本)

hello.i源程序  (文本)

hello.s汇编语 言程序  (文本)

hello.o可重定 位目标 程序(二进制)

链接	hello(ld)	可执行目标程序 (二进制)

## 第 4 页

预处理

预处理命令$gcc –E hello.c –o hello.i$cpp hello.c > hello.i处理源文件中以“#”开头的预编译指令，包括：删除“#define”并展开所定义的宏处理所有条件预编译指令，如“#if”,“#ifdef”, “#endif”等插入头文件到“#include”处，可以递归方式进行处理–	删除所有的注释“//”和“/* */”添加行号和文件名标识，以便编译时编译器产生调试用的行号信息保留所有#pragma编译指令（编译器需要用）经过预编译处理后，得到的是预处理文件（如，hello.i) ，它还是一个可读的文本文件 ，但不包含任何宏定义

## 第 5 页

预处理

#include "global.h"int f() {  return g+1;}

c1.c

global.h

#ifdef INITIALIZE  int g = 23;static int init = 1;  #elseint g;static int init = 0;  #endif

int g = 23;static int init = 1;  int f() {return g+1;}

int g;static int init = 0;  int f() {return g+1;}

定义 INITIALIZE

没有定义 INITIALIZE

#include指示被执行，插入.h文件的内容到源文件中

## 第 6 页

编译

编译过程就是将预处理后得到的预处理文件（如 hello.i）进行 词法分析、语法分析、语义分析、优化后，生成汇编代码文件用来进行编译处理的程序称为编译程序（编译器，Compiler）编译命令$gcc –S hello.i –o hello.s$gcc –S hello.c –o hello.s$/user/lib/gcc/i486-linux-gnu/4.1/cc1 hello.c经过编译后，得到的汇编代码文件（如 hello.s）还是可读的文 本文件，CPU无法理解和执行它gcc命令实际上是具体程序（如ccp、cc1、as等）的包装命令， 用户通过gcc命令来使用具体的预处理程序ccp、编译程序cc1和 汇编程序as等

## 第 7 页

汇编

汇编代码文件（由汇编指令构成）称为汇编语言源程序汇编程序（汇编器）用来将汇编语言源程序转换为机器指令序列（机器语言程序）汇编指令和机器指令一一对应，前者是后者的符号表示，它们都 属于机器级指令，所构成的程序称为机器级代码汇编命令$gcc –c hello.s –o hello.o$gcc –c hello.c –o hello.o$as hello.s -o hello.o	（as是一个汇编程序）汇编结果是一个可重定位目标文件（如，hello.o），其中包含 的是不可读的二进制代码，必须用相应的工具软件来查看其内容

## 第 8 页

链接

预处理、编译和汇编三个阶段针对一个模块（一个*.c文件）进行处理，得到对应的一个可重定位目标文件（一个*.o文件）链接过程将多个可重定位目标文件合并以生成可执行目标文件链接命令$gcc –static –o myproc main.o test.o$ld –static –o myproc main.o test.o–static 表示静态链接，如果不指定-o选项，则可执行文件名 为“a.out”主要介绍如何进行程序模块的链接

## 第 9 页

链接器的由来

1：0010 01012： ……3： ……4： ……5：0110 01116： ……

原始的链接概念早在高级编程语言出现之前就已存在最早程序员用机器语言编写程序，并记录在纸带或卡片上穿孔表示0，未穿孔为1 假设：0010-jmp0：0101 0110

若在第5条指令前加入 指令，则程序员需重新 计算jmp指令的目标地 址（重定位），然后重 新打孔。

太原始了，无法忍受，咋办？用符号表示而不用0/1表示！

## 第 10 页

用符号表示跳转位置和变量位置，是否简化了问题？

汇编语言出现用助记符表示操作码用符号表示位置用助记符表示寄存器–	…..更高级编程语言出现

程序越来越复杂，需多人开发不同的程序模块子程序（函数）起始地址和变量起始地址是符号定义（definition）调用子程序（函数或过程）和使用变量即是符号的引用（reference）一个模块定义的符号可以被另一个模块引用最终须链接（即合并），合并时须在符号引用处填入定义处的地址 如上例，先确定L0的地址，再在jmp指令中填入L0的地址

链接器的由来

0：0101 01101：0010 01012： ……3： ……4： ……5：0110 01116： ……

add B  jmp L0………………  L0：sub C……

## 第 11 页

可执行文件的生成

使用GCC编译器编译并链接生成可执行程序P:–	$ gcc -O2 -g -o p main.c swap.c–	$ ./p

链接 (ld)

程序转换 (cpp, cc1, as)

main.o

程序转换 (cpp, cc1, as)

main.c	swap.c

swap.o

源程序文件

分别转换（预处理、编 译、汇编）为可重定位 目标文件

可执行目标文件

GCC编译 器的 静态 链接 过程

-O2：2级优化-g：生成调试信息-o：目标文件名

## 第 12 页

链接过程的本质

main()

main.o

int *bufp0=&buf[0]

swap()

swap.o

系统代码

int buf[2]={1,2}

系统数据

.text.data

.text.data

int buf[2]={1,2}

可执行目标文件Headers

swap()

int *bufp0=&buf[0]

更多系统代码

系统数据

.text

.symtab.debug

.data

int *bufp1

.bss

系统代码main()

static int *bufp1

.text.data.bss

链接本质：合并相同的“节”可重定位目标文件

## 第 13 页

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

## 第 14 页

目标文件

00000000 <add>:0:	551:	89 e53:	83 ec 10	sub6:	8b 45 0c9:	8b 55 08c:	8d 04 02f:	89 45 fc12:	8b 45 fc15:	c916:	c3

$0x10, %espmov		0xc(%ebp), %eax  mov		0x8(%ebp), %edx  lea	(%edx,%eax,1), %eax  mov		%eax, -0x4(%ebp)  mov		-0x4(%ebp), %eax  leaveret

080483d480483d4:80483d5:80483d7:80483da:80483dd:80483e0:80483e3:80483e6:80483e9:80483ea:

<add>:  5589 e583 ec 108b 45 0c8b 55 088d 04 0289 45 fc8b 45 fc  c9c3

mov	-0x4(%ebp), %eax  leaveret

objdump -d test.opush	%ebpmov	%esp, %ebp

objdump -d testpush	%ebpmov		%esp, %ebp  sub	$0x10, %espmov		0xc(%ebp), %eax  mov		0x8(%ebp), %edx  lea	(%edx,%eax,1), %eax  mov		%eax, -0x4(%ebp)

/* main.c */int add(int, int);  int main( ){return add(20, 13);}

/* test.c */int add(int i, int j){int x = i + j;  return x;}

## 第 15 页

链接操作的步骤

1）确定符号引用关系（符号解析）

合并相关.o文件确定每个符号的地址在指令中填入新地址

代 码

数 据

P0: add Bjmp L0……  call P1……  L0:	sub C

……

P1:	add A………………  sub B

……

B:	10C：	20A:	30

P1:	add A………………  sub B……A:	30P1.o

P0: add Bjmp L0……  call P1……  L0:	sub C……B:	10C：	20

P0.o

重 定 位

## 第 16 页

链接操作的步骤

Step 1. 符号解析（Symbol resolution）程序中有定义和引用的符号 (包括变量和函数等)void swap() {…}	/* 定义符号swap */

swap();int *xp = &x;

/* 引用符号swap *//* 定义符号 xp, 引用符号 x */

编译器将定义的符号存放在一个符号表（ symbol table）中.符号表是一个结构数组每个表项包含符号名、长度和位置等信息链接器将每个符号的引用都与一个确定的符号定义建立关联Step 2. 重定位将多个代码段与数据段分别合并为一个单独的代码段和数据段计算每个定义的符号在虚拟地址空间中的绝对地址将可执行文件中符号引用处的地址修改为重定位后的地址信息

add B  jmp L0………………  L0：sub C……

## 第 17 页

使用链接的好处

链接带来的好处1：模块化一个程序可以分成很多源程序文件可构建公共函数库，如数学库，标准C库等（代码重用，开发效率高）链接带来的好处2：效率高时间上，可分开编译只需重新编译被修改的源程序文件，然后重新链接空间上，无需包含共享库所有代码源文件中无需包含共享库函数的源码，只要直接调用即可（如，只要直接调用printf()函数，无需包含其源码）  可执行文件和运行时的内存中只需包含所调用函数的代码 而不需要包含整个共享库

## 第 18 页

目标文件格式概述

## 第 19 页

三类目标文件

可重定位目标文件 (.o)其代码和数据可和其他可重定位文件合并为可执行文件每个.o 文件由对应的.c文件生成每个.o文件代码和数据地址都从0开始可执行目标文件 (默认为a.out)包含的代码和数据可以被直接复制到内存并被执行代码和数据地址为虚拟地址空间中的地址共享的目标文件 (.so)特殊的可重定位目标文件，能在装入或运行时被装入到内 存并自动被链接，称为共享库文件

## 第 20 页

目标文件的格式

目标代码（Object Code）指编译器和汇编器处理源代码后所生 成的机器语言目标代码目标文件（Object File）指包含目标代码的文件最早的目标文件格式是自有格式，非标准的标准的几种目标文件格式DOS操作系统（最简单） ：COM格式，文件中仅包含代码和数据，  且被加载到固定位置System V UNIX早期版本：COFF格式，文件中不仅包含代码和数据，还包含重定位信息、调试信息、符号表等其他信息，由一组严格定 义的数据结构序列组成Windows： PE格式（COFF的变种），称为可移植可执行（  Portable Executable，简称PE）Linux等类UNIX：ELF格式（COFF的变种），称为可执行可链接（  Executable and Linkable Format，简称ELF）

## 第 21 页

Executable and Linkable Format (ELF)

两种视图链接视图（被链接）：可重定位目标文件 (Relocatable object files)执行视图（被执行）：可执行目标文件（Executable object files）

节（section）是 ELF 文件中具有相 同特征的最小可处 理单位.text节: 代码.data节: 数据.rodata: 只读数据.bss: 未初始化数据

由不同的段（  segment）组 成，描述节如 何映射到存储 段中，可多个节映射到同一 段，如：可合并.data节和.bss节,并映射到一个可读可写数据段中

链接视图

执行视图

## 第 22 页

链接视图—可重定位目标文件

可被链接（合并）生成可执行文件或共享目标文件静态链接库文件由若干个可重定位目标文件组成包含代码、数据（已初始化.data和未初始化.bss）包含重定位信息（指出哪些符号引用处需要重定位）文件扩展名为.o（相当于Windows中的 .obj文件）

int x=100;  int y;void prn(int n){printf(“%d\n”,n);}void main( ){static int a=1;  static int b;  int i=200,j;  prn(x+a+i);}

ELF的链接视图

.text节

.data节

.bss节

为了进行链接，还需要其他许多信 息，如符号表、重定位信息等许多 其他的节（Section）

## 第 23 页

执行视图—可执行目标文件

包含代码、数据（已初始化.data和未初始化.bss）定义的所有变量和函数已有确定地址（虚拟地址空间中的地址）符号引用处已被重定位，以指向所引用的定义符号没有文件扩展名或默认为a.out（相当于Windows中的 .exe文件）可被CPU直接执行，指令地址和指令给出的操作数地址都是虚拟地址

为了能执行，还需将具相同访问属性的节合并成段（Segment），并说明每个段的属性， 如：在可执行文件中的位移、大小、在虚拟空间中的位置、对齐方式、访问属性等

int x=100;  int y;void prn(int n){printf(“%d\n”,n);}void main( ){static int a=1;  static int b;  int i=200,j;  prn(x+a+i);}

ELF的执行视图

.text节

.data节

.bss节

程序头 表用来 说明段 信息， 也称段 头表

## 第 24 页

ELF可重定位目标文件

## 第 25 页

未初始化变量（.bss节）

C语言规定：未初始化的全局变量和局部静态变量的默认初始值为0将未初始化变量（.bss节）与已初始化变量（.data节）分开的 好处.data节中存放具体的初始值，需要占磁盘空间.bss节中无需存放初始值，只要说明.bss中的每个变量将来 在执行时占用几个字节即可，因此，.bss节实际上不占用磁 盘空间，提高了磁盘空间利用率BSS（Block Started by Symbol）最初是UA-SAP汇编程序 中所用的一个伪指令，用于为符号预留一块内存空间所有未初始化的全局变量和局部静态变量都被汇总到.bss节中， 通过专门的“节头表（Section header table）”来说明应该 为.bss节预留多大的空间

## 第 26 页

可重定位目标文件格式

ELF 头包括16字节标识信息、文件类型 (.o,  exec, .so)、机器类型（如 IA-32）、 节头表的偏移、节头表的表项大小以及 表项个数.text 节编译后的代码部分.rodata 节只读数据，如 printf 格式串、switch跳 转表等.data 节已初始化的全局变量.bss 节未初始化全局变量，仅是占位符，不占 据任何实际磁盘空间。区分初始化和非 初始化是为了空间效率

.symtab 节.rel.txt 节.rel.data 节.debug 节

Section header table（节头表）

ELF 头.text 节.rodata 节.data 节.bss 节

.strtab 节.line 节

## 第 27 页

可重定位目标文件格式

.symtab 节(符号表节)存放函数和全局变量 （符号表）信息 ，  它不包括局部变量.rel.text 节.text节的重定位信息，用于重新修改代 码段的指令中的地址信息.rel.data 节.data节的重定位信息，用于对被模块使 用或定义的全局变量进行重定位的信息.debug 节调试用符号表 (gcc -g)  strtab 节(字符串表节)包含symtab和debug节中符号及节名 Section header table（节头表）每个节的节名、偏移和大小

.symtab 节.rel.txt 节.rel.data 节.debug 节

Section header table（节头表）

ELF 头.text 节.rodata 节.data 节.bss 节

.strtab 节.line 节

## 第 28 页

ELF头（ELF Header）

ELF头位于ELF文件开始，包含文件结构说明信息。分32位系统对应结构 和64位系统对应结构（32位版本、64位版本）

以下是32位系统对应的数据结构

16e_ident[EI_NIDENT];  e_type;e_machine;  e_version;  e_entry;  e_phoff;  e_shoff;

e_flags;  e_ehsize;  （ELF头的大小）e_phentsize;  e_phnum;  e_shentsize;  e_shnum;  e_shstrndx;

#define EI_NIDENT  typedef struct {unsigned char  Elf32_Half  Elf32_Half  Elf32_Word  Elf32_Addr  Elf32_Off  Elf32_Off  Elf32_Word  Elf32_Half  Elf32_Half  Elf32_Half  Elf32_Half  Elf32_Half  Elf32_Half} Elf32_Ehdr;

定义了ELF魔数、版本、小 端/大端、操作系统平台、 目标文件的类型、机器结构 类型、程序执行的入口地址、程序头表（段头表）的起 始位置和长度、节头表的起 始位置和长度等

## 第 29 页

ELF头信息举例

$ readelf -h main.o

ELF Header:

00

Magic:	7f 45 4c 46 01 01 01 00 00 00 00 00 00 00 00Class:	ELF32

Data:	2's complement, little endian  Version: 1 (current)

OS/ABI:	UNIX - System V  ABI Version:	0Type:	REL (Relocatable file) 	 Machine:	Intel 80386

Version:	0x1

Entry point address:	0x0

Start of program headers:	0 (bytes into file)

Start of section headers:	516 (bytes into file)

Flags:	0x0Size of this header:	52 (bytes)Size of program headers:	0 (bytes)

Number of program headers:	0  Size of section headers:	40 (bytes)

Number of section headers:	15

Section header string table index: 12

.symtab 节.rel.txt 节.rel.data 节.debug 节

Section header（节头表）

ELF 头.text 节.rodata 节.data 节.bss 节

.strtab 节.line 节

可重定位目标文件的ELF头

没有程序头表

15x40B.strtab在节头 表中的索引

ELF文件的魔数

## 第 30 页

节头表（Section Header Table）

除ELF头之外，节头表是ELF可重定位目标文件中最重要的部分内容描述每个节的节名、在文件中的偏移、大小、访问属性、对齐方式等以下是32位系统对应的数据结构（每个表项占40B）typedef struct {

sh_link;

Elf32_Word  Elf32_Word  Elf32_Word  Elf32_Addr  Elf32_Off  Elf32_Word  Elf32_Word  Elf32_Word  Elf32_Word  Elf32_Word} Elf32_Shdr;

sh_name;	节名字符串在.strtab中的偏移sh_type;		节类型：无效/代码或数据/符号/字符串/…  sh_flags;			节标志：该节在虚拟空间中的访问属性 sh_addr;			虚拟地址：若可被加载，则对应虚拟地址 sh_offset; 在文件中的偏移地址，对.bss节而言则无意义 sh_size;	节在文件中所占的长度

sh_link和sh_info用于与链接相关的节（如

sh_info;	.rel.text节、.rel.data节、.symtab节等）sh_addralign;	节的对齐要求

sh_entsize; 节中每个表项的长度，0表示无固定长度表项

## 第 31 页

节头表信息举例

$ readelf -S test.oThere are 11 section headers, starting at offset 0x120:

PROGBITS   00000000  000034  00005b  00  AX 0REL	00000000  000498  000028   08	9

PROGBITS  00000000 000090 00000c     00 WA 0

NOBITS	00000000 00009c 00000c     00 WA 0

Section Headers:  [Nr] Name[ 0][ 1] .text[ 2] .rel.text[ 3] .data[ 4] .bss[ 5] .rodata[ 6] .comment

[ 7] .note.GNU-stack PROGBITS 00000000 0000ce  000000   00

00000000 0000ce 000051       00

PROGBITS  00000000  00009c  000004    00	A    0PROGBITS  00000000  0000a0  00002e    00        000

Type	Addr	Off	Size	ES Flg Lk Inf Al  NULL        00000000  000000 000000 00	0	0 00 41 40 40 40 10 10 10 1

00000000 0002d8 000120   10

STRTAB  SYMTAB  STRTAB

00000000 0003f8 00009e    00

10 13 40	0 1

[ 8] .shstrtab[ 9] .symtab[10] .strtab  Key to Flags:

W (write), A (alloc), X (execute), M (merge), S (strings)  I (info), L (link order), G (group), x (unknown)O (extra OS processing required) o (OS specific), p (processor specific)

.symtab 节.rel.txt 节.rel.data 节.debug 节

Section header（节头表）

ELF 头.text 节.rodata 节.data 节.bss 节

.strtab 节.line 节

可重定位目标文件中，每个可装入节的起始地址总是0

## 第 32 页

节头表信息举例

$ readelf -S test.oThere are 11 section headers, starting at offset 0x120:

Section Headers:  [Nr] Name

Off

Size

ES Flg Lk Inf Al

[ 3] .data	000090  00000c  00 WA  0	0 4  [ 4] .bss	00009c  00000c  00 WA  0	0 4  [ 5] .rodata	00009c  000004 00	A	0	0 1

[ 6] .comment	0000a0  00002e 00[ 7] .note.GNU-stack  0000ce  000000 00

0	0 10	0 10	0 1

0000ce  000051 000002d8  000120 100003f8 00009e 00

10 13 40	0 1

[ 8] .shstrtab[ 9] .symtab[10] .strtab  Key to Flags:

W (write), A (alloc), X (execute), M (merge), S (strings)  I (info), L (link order), G (group), x (unknown)

………..

有4个节将会分配存储空间.text：可执行.data和.bss：可读可写.rodata：可读

ELF头e_shoff=0x120

.text

.data

.rodata

.comment

.shstrtab

节头表

.symtab

.strtab

.rel.text

000000

0000ce

.bss

0002d8

0003f8

00011f000120

5b

0c

04

0c

2e

51

1b8

120

9e

28

00003400008f00009000009c0000a0

000496000498

可重定位目标文件test.o的结构

## 第 33 页

ELF可执行目标文件

## 第 34 页

可执行目标文件格式

ELF 头

.text 节.rodata 节

.bss 节

程序头表

.init 节

.symtab 节.debug 节

Section header table（节头表）

.data 节

.strtab 节.line 节

只读 (代码)段

读写 (数据)段

无需 装入 到存 储空 间的 信息

与可重定位文件稍有不同：ELF头中字段e_entry给出执 行程序时第一条指令的地址， 而在可重定位文件中，此字段 为0多一个程序头表，也称段头表（segment header table），是一个结构数组多一个.init节，用于定义_init函数，该函数用来进行 可执行目标文件开始执行时的 初始化工作少两个.rel节（无需重定位）

## 第 35 页

ELF头信息举例

$ readelf -h main

ELF Header:

00 00

Magic:	7f 45 4c 46 01 01 01 00 00 00 00 00 00 00Class:	ELF32Data:	2's complement, little endian

Version:	1 (current)

OS/ABI:	UNIX - System V

ABI Version:	0Type:	EXEC (Executable file) 	 Machine:	Intel 80386

Version:	0x1Entry point address:	x8048580

Start of program headers:		52 (bytes into file)  Start of section headers:	3232 (bytes into file)  Flags:	0x0

Size of this header:	52 (bytes)Size of program headers:	32 (bytes)

Number of program headers:		8  Size of section headers:	40 (bytes)  Number of section headers:	29

Section header string table index: 26

可执行目标文件的ELF头

ELF 头

.text 节.rodata 节

.bss 节

程序头表

.init 节

.symtab 节.debug 节

Section header table（节头表）

.data 节

.strtab 节.line 节

29x40B

8x32B

## 第 36 页

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

## 第 37 页

可执行文件中的程序头表

p_type;  p_offset;  p_vaddr;  p_paddr;  p_filesz;  p_memsz;  p_flags;  p_align;

typedef struct {Elf32_Word  Elf32_Off  Elf32_Addr  Elf32_Addr  Elf32_Word  Elf32_Word  Elf32_Word  Elf32_Word} Elf32_Phdr;

程序头表描述可执行文件中的节与虚拟 空间中的存储段之间的映射关系一个表项（32B）说明虚拟地址空间中 一个连续的段或一个特殊的节以下是某可执行目标文件程序头表信息有8个表项，其中两个为可装入段（即  Type=LOAD）

$ readelf –l main

## 第 38 页

可执行文件中的程序头表

SKIP第一可装入段：第0x00000~0x004d3字节（包括ELF头、程序头表、.init、.text和.rodata节），映射到虚拟地址0x8048000开始长度为0x4d4字节的区域，按0x1000=212=4KB对齐，具有只读/执行权限（Flg=RE），是只读代码段。第二可装入段：第0x000f0c开始长度为0x108字节的.data节，映射到虚拟地址 0x8049f0c开始长度为0x110字节的存储区域，在0x110=272B存储区中，前0x108=264B用.data节内容初始化，后面272-264=8B对应.bss节，初始化为0，按0x1000=4KB对齐，具有可读可写权限（Flg=RW），是可读写数据段。

## 第 39 页

可执行文件的存储器映像

00000

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

BACK

1GB

004d300f0c  010140101c

0x08049000

## 第 40 页

符号及符号表

## 第 41 页

回顾：链接操作的步骤

1）确定符号引用关系（符号解析）

合并相关.o文件确定每个符号的地址在指令中填入新地址

代 码

数 据

P0: add Bjmp L0……  call P1……  L0:	sub C

……

P1:	add A………………  sub B

……

B:	10C：	20A:	30

P1:	add A………………  sub B……A:	30P1.o

P0: add Bjmp L0……  call P1……  L0:	sub C……B:	10C：	20

P0.o

重 定 位

## 第 42 页

回顾：链接操作的步骤

Step 1. 符号解析（Symbol resolution）程序中有定义和引用的符号 (包括变量和函数等)void swap() {…}	/* 定义符号swap */

swap();int *xp = &x;

/* 引用符号swap *//* 定义符号 xp, 引用符号 x */

编译器将定义的符号存放在一个符号表（ symbol table）中.符号表是一个结构数组每个表项包含符号名、长度和位置等信息链接器将每个符号的引用都与一个确定的符号定义建立关联Step 2. 重定位将多个代码段与数据段分别合并为一个单独的代码段和数据段计算每个定义的符号在虚拟地址空间中的绝对地址将可执行文件中符号引用处的地址修改为重定位后的地址信息

add B  jmp L0………………  L0：sub C……

## 第 43 页

符号的定义和引用

int buf[2] = {1, 2};  void swap();int main(){swap();  return 0;}

main.c

swap.c

extern int buf[];int *bufp0 = &buf[0];  static int *bufp1;void swap(){int temp;bufp1 = &buf[1];  temp = *bufp0;*bufp0 = *bufp1;*bufp1 = temp;}

你能说出哪些是符号定义？哪些是符号的引用？局部变量temp分配在栈中，不会在过程外被引用，因此不是符号定义

## 第 44 页

链接符号的类型

每个可重定位目标模块m都有一个符号表，它包含了在m中定义和引用的 符号。有三种链接器符号：Global symbols（模块内部定义的全局符号）由模块m定义并能被其他模块引用的符号。例如，非static C函数和非 static的C全局变量（指不带static的全局变量）如，main.c 中的全局变量名bufExternal symbols（外部定义的全局符号）	由其他模块定义并被模块m引用的全局符号 如，main.c 中的函数名swapLocal symbols（本模块的局部符号）仅由模块m定义和引用的本地符号。例如，在模块m中定义的带static  的C函数和全局变量如，swap.c 中的static变量名bufp1链接器局部符号不是指程序中的局部变量（分配在栈中的临 时性变量）,链接器不关心这种局部变量

## 第 45 页

链接符号类型举例

int buf[2] = {1, 2};  void swap();int main(){swap();  return 0;}

main.c

extern int buf[];int *bufp0 = &buf[0];  static int *bufp1;void swap(){int temp;bufp1 = &buf[1];  temp = *bufp0;*bufp0 = *bufp1;*bufp1 = temp;}

swap.c

你能说出哪些是全局符号？哪些是外部符号？哪些是局部符号？

## 第 46 页

目标文件中的符号表

typedef	struct {

st_name;	/*符号对应字符串在strtab节中的偏移量*/

Elf32_Word  Elf32_Addr  Elf32_Word

st_value;		/*在对应节中的偏移量，或虚拟地址*/  st_size;	/*符号对应目标字节数*/

unsigned char	st_info;  unsigned char	st_other;

st_shndx;	/*符号对应目标所在的节，或其他情况*/

Elf32_Half} Elf32_Sym;

.symtab 节记录符号表信息，是一个结构数组

函数名在text节中

符号表（symtab）中每个表项（16B）的结构如下： 变量名在data节或

bss节中

函数大小或变量长度

/*指出符号的类型(Type)和绑定属性(Bind) */

其他情况：ABS表示不该被重定位；UND表示未定义；COM表示未初 始化数据（.bss），此时，value表示对齐要求，size给出最小大小符号类型（Type）：数据、函数、源文件、节、未知 绑定属性（Bind）：全局符号、局部符号、弱符号

## 第 47 页

符号表信息举例

main.o中的符号表中最后三个条目（共10个）

buf是main.o中第3节（.data）偏移为0的符号，是全局变量，占8B；  main是第1节（.text）偏移为0的符号，是全局函数，占33B；swap是未定义的符号，不知道类型和大小，全局的（在其他模块定义）swap.o中的符号表中最后4个条目（共11个）

bufp1是未分配地址且未初始化的本地变量(ndx=COM), 按4B对齐且占4B

## 第 48 页

符号解析（Symbol Resolution）

目的：将每个模块中引用的符号与某个目 标模块中的定义符号建立关联。每个定义符号在代码段或数据段中都被分 配了存储空间，将引用符号与定义符号建 立关联后，就可在重定位时将引用符号的 地址重定位为相关联的定义符号的地址。本地符号在本模块内定义并引用，因此， 其解析较简单，只要与本模块内唯一的定 义符号关联即可。全局符号（外部定义的、内部定义的）的 解析涉及多个模块，故较复杂。

“符号的定义”其 实质是什么？

add B  jmp L0……  L0：sub 23……  B：	……确定L0的地址， 再在jmp指令中 填入L0的地址

指被分配了存储空间。为函数名即指其代码 所在区；为变量名即指其所占的静态数据区。所有定义符号的值就是其目标所在的首地址

符号解析也称符号绑定

## 第 49 页

全局符号的强、弱

int var=5;p1() {……}

int var;p2() {……}

p1.c

p2.c

全局符号的强/弱特性函数名和已初始化的全局变量名是强符号未初始化的全局变量名是弱符号以下符号哪些是强符号？哪些是弱符号？

## 第 50 页

全局符号的强、弱

int buf[2] = {1, 2};  void swap();int main(){swap();  return 0;}

main.c

extern int buf[];int *bufp0 = &buf[0];  static int *bufp1;void swap(){int temp;bufp1 = &buf[1];  temp = *bufp0;*bufp0 = *bufp1;*bufp1 = temp;}

swap.c

此处为引用

本地局部符号

局部变量

以下符号哪些是强符号？哪些是弱符号？

## 第 51 页

链接器对符号的解析规则

多重定义符号的处理规则Rule 1: 强符号不能多次定义强符号只能被定义一次，否则链接错误Rule 2: 若一个符号被定义为一次强符号和多次弱符号，则 按强定义为准对弱符号的引用被解析为其强定义符号 Rule 3: 若有多个弱符号定义，则任选其中一个使用命令 gcc –fno-common链接时，会告诉链接器在 遇到多个弱定义的全局符号时输出一条警告信息。符号解析时只能有一个确定的定义（即每个符号仅占一处存储空间）

## 第 52 页

多重定义符号的解析举例

int	x=10;  int	p1(void);  int main(){x=p1();return x;}main.c

int	x=20;  int p1(){return x;}p1.c

main只有一次强定义

p1有一次强定义，一次弱 定义x有两次强定义，所以，链 接器将输出一条出错信息

以下程序会发生链接出错吗？

## 第 53 页

多重定义符号的解析举例

y一次强定义，一次弱定义  z两次弱定义p1一次强定义，一次弱定义  main一次强定义int	y;int	z;  void p1( ){y=200;  z=2000;}p1.c

问题：打印结果是什么？y=200，z=2000

以下程序会发生链接出错吗？# include <stdio.h>  int	y=100;int	z;void	p1(void);  int main(){z=1000;  p1( );printf(“y=%d, z=%d\n”, y, z);  return 0;}main.c

该例说明：在两个不同模块定义相同变 量名，很可能发生意想不到的结果 ！

## 第 54 页

多重定义符号的解析举例

以下程序会发生链接出错吗？1	#include <stdio.h>  2	int d=100;3	int x=200;void p1(void);int main()  6	{7	p1();printf(“d=%d,x=%d\n”,d,x);return 0;10	}main.c问题：打印结果是什么？

p1.c1	double d;  23	void p1()  4	{5	d=1.0;6	}

p1执行后d和x处内容是什么？

FLD1FSTPl	&d

1.0：0 01111111111 0…0B=3FF0 0000 0000 0000H

## 第 55 页

多重定义符号的解析举例

打印结果：d=0，x=1 072 693 248Why？

…….1	int d=100;2	int x=200;3	int main()  4	{5	p1( );printf (“d=%d, x=%d\n”, d, x );return 0;  8	}

main.c

p1.c

1	double d;  23	void p1( )  4	{5	d=1.0;6	}double型数1.0对应的机器数  3FF0 0000 0000 0000H

IA-32是小端方式

230-1-(220-1)=230-220=1024*1024*1023=1 072 693 248

## 第 56 页

多重定义符号的解析举例

以下程序会发生链接出错吗？1	#include <stdio.h>  2	int d=100;3	int x=200;void p1(void);int main()  6	{7	p1();printf(“d=%d,x=%d\n”,d,x);return 0;10	}main.c问题：打印结果是什么？d=0,x=1 072 693 248该例说明：两个重复定义的变量具有不同 类型时，更容易出现难以理解的结果 !

p1.c1	double d;  23	void p1()  4	{5	d=1.0;6	}

p1执行后d和x处内容是什么？

FLD1FSTPl	&d

1.0：0 01111111111 0…0B=3FF0 0000 0000 0000H

## 第 57 页

多重定义全局符号的问题

尽量避免使用全局变量一定需要用的话，就按以下规则使用尽量使用本地变量（static）全局变量要赋初值外部全局变量要使用extern多重定义全局变量会造成一些意想不到的错误，而且是默默发生 的，编译系统不会警告，并会在程序执行很久后才能表现出来，  且远离错误引发处。特别是在一个具有几百个模块的大型软件中， 这类错误很难修正。大部分程序员并不了解链接器如何工作，因而养成良好的编程习 惯是非常重要的。

## 第 58 页

静态链接和符号解析

## 第 59 页

回顾：链接操作的步骤

Step 1. 符号解析（Symbol resolution）程序中有定义和引用的符号 (包括变量和函数等)void swap() {…}	/* 定义符号swap */

swap();int *xp = &x;

/* 引用符号swap *//* 定义符号 xp, 引用符号 x */

编译器将定义的符号存放在一个符号表（ symbol table）中.符号表是一个结构数组每个表项包含符号名、长度和位置等信息链接器将每个符号的引用都与一个确定的符号定义建立关联Step 2. 重定位将多个代码段与数据段分别合并为一个单独的代码段和数据段计算每个定义的符号在虚拟地址空间中的绝对地址将可执行文件中符号引用处的地址修改为重定位后的地址信息

add B  jmp L0……

…………  L0：sub C……

## 第 60 页

如何划分模块？

静态链接对象：多个可重定位目标模块 + 静态库（标准库、自定义库）（.o文件）	（.a文件，其中包含多个.o模块）库函数模块：许多函数无需自己写，可使用共享的库函数如数学库, 输入/输出库, 存储管理库，字符串处理等对于自定义模块，避免以下两种极端做法将所有函数都放在一个源文件中修改一个函数需要对所有函数重新编译时间和空间两方面的效率都不高一个源文件中仅包含一个函数需要程序员显式地进行链接效率高，但模块太多，故太繁琐

## 第 61 页

静态共享库

静态库 (.a archive files)将所有相关的目标模块（.o）打包为一个单独的库文件（.a），称为静态库文件 ，也称存档文件（archive）使用静态库，可增强链接器功能，使其能通过查找一个 或多个库文件中定义的符号来解析符号在构建可执行文件时，只需指定库文件名，链接器会自 动到库中寻找那些应用程序用到的目标模块，并且只把 用到的模块从库中拷贝出来在gcc命令行中无需明显指定C标准库libc.a(默认库)

## 第 62 页

静态库的创建

转换 (cpp,cc1,as)

atoi.c

atoi.o

转换 (cpp,cc1,as)

printf.c

printf.o

Archiver (ar)

...

random.c

random.o

$ ar rs libc.a \atoi.o printf.o … random.o

libc.a	C标准静态库Archiver（归档器）允许增量更新，只要重新编译需修改的源 码并将其.o文件替换到静态库中。

转换 (cpp,cc1,as)

## 第 63 页

常用静态库

libc.a ( C标准库 )1392个目标文件（大约8 MB）包含I/O、存储分配、信号处理、字符串处理、时间和日期、随机 数生成、定点整数算术运算libm.a (the C math library)401 个目标文件（大约 1 MB）浮点数算术运算(如sin, cos, tan, log, exp, sqrt, …)

% ar -t /usr/lib/libc.a | sort…  fork.o…fprintf.o  fpu_control.o  fputc.o  freopen.o  fscanf.o  fseek.o  fstab.o…

% ar -t /usr/lib/libm.a | sort…  e_acos.o  e_acosf.o  e_acosh.o  e_acoshf.o  e_acoshl.o  e_acosl.o  e_asin.o  e_asinf.o  e_asinl.o…

## 第 64 页

自定义一个静态库文件

$ ar rcs mylib.a myproc1.o myproc2.o

myproc1.c# include <stdio.h>  void myfunc1() {printf("This is myfunc1!\n");}$ gcc –c myproc1.c myproc2.c

myproc2.c# include <stdio.h>  void myfunc2() {printf("This is myfunc2\n");}

举例：将myproc1.o和myproc2.o打包生成mylib.a

main.cvoid myfunc1(viod);  int main(){myfunc1();  return 0;}

$ gcc –c main.c

$ gcc –static –o myproc main.o ./mylib.a调用关系：main→myfunc1→printf

libc.a无需明显指出！

问题：如何进行符号解析？

## 第 65 页

链接器中符号解析的全过程

$ gcc –c main.c

$ gcc –static –o myproc main.o ./mylib.a

调用关系：main→myfunc1→printfE 将被合并以组成可执行文件的所有目标文件集合 U 当前所有未解析的引用符号的集合D 当前所有定义符号的集合开始E、U、D为空，首先扫描main.o，把它加入E，  同时把myfunc1加入U，main加入D。接着扫描到 mylib.a，将U中所有符号（本例中为myfunc1）与 mylib.a中所有目标模块（myproc1.o和myproc2.o）依次匹配，发现在myproc1.o中定义了myfunc1，故myproc1.o加入E，myfunc1从U转移到D。在 myproc1.o中发现还有未解析符号printf，将其加到 U。不断在mylib.a的各模块上进行迭代以匹配U中的 符号，直到U、D都不再变化。此时U中只有一个未解 析符号printf，而D中有main和myfunc1。因为模块 myproc2.o没有被加入E中，因而它被丢弃。

main.cvoid myfunc1(viod);  int main(){myfunc1();  return 0;}接着，扫描默认的库 文件libc.a，发现其目 标模块printf.o定义了  printf，于是printf也 从U移到D，并将 printf.o加入E，同时 把它定义的所有符号 加入D，而所有未解 析符号加入U。处理完libc.a时，U一 定是空的。

libc.a无需明显指出！

## 第 66 页

链接器中符号解析的全过程

main.cvoid myfunc1(viod);  int main(){myfunc1();  return 0;}

$ gcc –static –o myproc main.o ./mylib.a

解析结果：

E中有main.o、myproc1.o、printf.o及其调用的模块 D中有main、myproc1、printf及其引用的符号

main→myfunc1→printf

转换 (cpp,cc1,as)

main.c

main.o

转换 (cpp,cc1,as)

printf.o及其 调用模块

myproc

静态链接器(ld)

...

myproc1.o

完全链接的可 执行目标文件

转换 (cpp,cc1,as)

自定义静态库mylib.a

标准静态库Libc.a

注意：E中无  myproc2.o

## 第 67 页

链接器中符号解析的全过程

若命令为：$ gcc –static –o myproc ./mylib.a main.o， 结果怎样？

因此，出现链接错误！

main.cvoid myfunc1(viod);  int main(){myfunc1();  return 0;}main→myfunc1→printf

$ gcc –static –o myproc main.o ./mylib.a解析结果：E中有main.o、myproc1.o、printf.o及其调 用的模块D中有main、myproc1、printf及其引用符号被链接模块应按 调用顺序指定！

首先，扫描mylib，因是静态库，应根据其中是否存在U中未解析符号对应 的定义符号来确定哪个.o被加入E。因为开始U为空，故其中两个.o模块都不 被加入E中而被丢弃。然后，扫描main.o，将myfunc1加入U，直到最后它都不能被解析。Why？它只能用mylib.a中符号来解析，而

mylib中两个.o模块都已被丢弃！

## 第 68 页

使用静态库

$ gcc -L. libtest.o -lmine$ gcc -L. -lmine libtest.o

libtest.o: In function `main':libtest.o(.text+0x4): undefined reference to `libfun'说明在libtest.o中的main调用了libfun这个在库libmine中的函数，  所以，在命令行中，应该将libtest.o放在前面，像第一行中那样 !

扫描libtest.o，将libfun送U，扫描到 libmine.a时，用其定义的libfun来解析

链接器对外部引用的解析算法要点如下:按照命令行给出的顺序扫描.o 和.a 文件扫描期间将当前未解析的引用记录到一个列表U中每遇到一个新的.o 或 .a 中的模块，都试图用其来解析U中的符号如果扫描到最后，U中还有未被解析的符号，则发生错误问题和对策能否正确解析与命令行给出的顺序有关好的做法：将静态库放在命令行的最后	libmine.a 是静态库假设调用关系：libtest.o→libfun.o(在libmine.a中）-lxxx=libxxx.a	(main) →(libfun)

## 第 69 页

链接顺序问题

假设调用关系如下：func.o → libx.a 和 liby.a 中的函数 libx.a → libz.a 中的函数libx.a 和 liby.a 之间、liby.a 和 libz.a 相互独立 则以下几个命令行都是可行的：gcc -static –o myfunc func.o libx.a liby.a libz.agcc -static –o myfunc func.o liby.a libx.a libz.agcc -static –o myfunc func.o libx.a libz.a liby.a假设调用关系如下：func.o → libx.a 和 liby.a 中的函数 libx.a → liby.a 同时 liby.a → libx.a  则以下命令行可行：gcc -static –o myfunc func.o libx.a liby.a libx.a

## 第 70 页

符号的重定位

## 第 71 页

回顾：链接操作的步骤

Step 1. 符号解析（Symbol resolution）程序中有定义和引用的符号 (包括变量和函数等)void swap() {…}	/* 定义符号swap */

swap();int *xp = &x;

/* 引用符号swap *//* 定义符号 xp, 引用符号 x */

编译器将定义的符号存放在一个符号表（ symbol table）中.符号表是一个结构数组每个表项包含符号名、长度和位置等信息链接器将每个符号的引用都与一个确定的符号定义建立关联Step 2. 重定位将多个代码段与数据段分别合并为一个单独的代码段和数据段计算每个定义的符号在虚拟地址空间中的绝对地址将可执行文件中符号引用处的地址修改为重定位后的地址信息

add B  jmp L0………………  L0：sub C……

## 第 72 页

回顾：链接操作的步骤

代 码

P0: add Bjmp L0……  call P1……  L0:	sub C……

P1:	add A………………  sub B……B:	10C：	20A:	30

P1:	add A………………  sub B……A:	30

P0: add Bjmp L0……  call P1……  L0:	sub C

……

B:	10C：	20

%esp

brk

0xC00000000

数据 0x080480000

内核虚存区

共享库区域

堆（heap） 动态生成)

用户栈 动态生成

未使用

读写数据段(.data, .bss)

只读代码段(.text, .rodata等)

从可 执行 文件 装入

1GB

符号解析

同节合并

确定地址

修改引用

## 第 73 页

重定位

符号解析完成后，可进行重定位工作，分三步合并相同的节将集合E的所有目标模块中相同的节合并成新节例如，所有.text节合并作为可执行文件中的.text节对定义符号进行重定位（确定地址）确定新节中所有定义符号在虚拟地址空间中的地址例如，为函数确定首地址，进而确定每条指令的地址，为变量确定首地址完成这一步后，每条指令和每个全局或局部变量都可确定地址对引用符号进行重定位（确定地址）修改.text节和.data节中对每个符号的引用（地址）需要用到在.rel_data和.rel_text节中保存的重定位信息

## 第 74 页

重定位信息

IA-32有两种最基本的重定位类型–	R_386_32: 绝对地址–	R_386_PC32: PC相对地址

汇编器遇到引用时，生成一个重定位条目数据引用的重定位条目在.rel_data节中指令中引用的重定位条目在.rel_text节中ELF中重定位条目格式如下：typedef	struct {int	offset;		/*节内偏移*/  int	symbol:24,	/*所绑定符号*/

type: 8;	/*重定位类型*/} Elf32_Rel;

例如，在rel_text节中有重定位条目

offset: 0x1  symbol: Btype:	R_386_32

add B  jmp L0……  L0：sub 23……  B：	……

05 00000000

02 FCFFFFFF

……

offset: 0x6  symbol: L0type:	R_386_PC32

L0：sub 23……  B：	……重定位条目和汇编后的机器 代码在哪种目标文件中？在可重定位目标（.o）文件中！

## 第 75 页

重定位操作举例

int buf[2] = {1, 2};  void swap();int main(){swap();  return 0;}

main.c

swap.c

extern int buf[];int *bufp0 = &buf[0];  static int *bufp1;void swap(){int temp;bufp1 = &buf[1];  temp = *bufp0;*bufp0 = *bufp1;*bufp1 = temp;}

你能说出哪些是符号定义？哪些是符号的引用？局部变量temp分配在栈中，不会在过程外被引用，因此不是符号定义

## 第 76 页

符号引用的地址需要重定位

main()

main.o

int *bufp0=&buf[0]

swap()

swap.o

系统代码

int buf[2]={1,2}

系统数据

.text.data

.text.data

int buf[2]={1,2}

可执行目标文件Headers

main()

swap()

int *bufp0=&buf[0]

更多系统代码

系统数据

.text

.symtab.debug

.data

int *bufp1

.bss

系统代码

static int *bufp1

.text.data.bss

链接本质：合并相同的“节”可重定位目标文件

## 第 77 页

int buf[2]={1,2};int main(){swap();  return 0;}

main.o重定位前

main.c

main的定义在.text  节中偏移为0处开始， 占0x12B。

Disassembly of section .data:00000000 <buf>:0:	01 00 00 00 02 00 00 00

buf的定义在.data节中 偏移为0处开始，占8B。

在rel_text节中的重定位条目为：  r_offset=0x7, r_sym=10,  r_type=R_386_PC32，dump出 来后为“7: R_386_PC32 swap”r_sym=10说明引用的是swap！

main.o

Disassembly of section .text:  00000000 <main>:

push	%ebpmov	%esp,%ebpand	$0xfffffff0,%esp

call	7 <main+0x7>

7: R_386_PC32 swap

b8 00 00 00 00	mov	$0x0,%eax

0:	551:	89 e53:	83 e4 f06:	e8 fc ff ff ffb:10:	c911:	c3

leave  ret

## 第 78 页

main.o中的符号表

main.o中的符号表中最后三个条目

swap是main.o的符号表中第10项，是未定义符号，类型和大小 未知，并是全局符号，故在其他模块中定义。

在rel_text节中的重定位条目为：  r_offset=0x7, r_sym=10,  r_type=R_386_PC32，dump出 来后为“7: R_386_PC32 swap”

r_sym=10说明 引用的是swap！

BACK

## 第 79 页

R_386_PC32的重定位方式

假定：–	可执行文件中mai

–	swap紧跟main后

则swap起始地址为

n函数对应机器代码从0x8048380开始，其机器代码首地址按4字节边界对齐多少？

–	0x8048380+0x12=0x8048392

–	在4字节边界对齐的情况下，是0x8048394

则重定位后call指令的机器代码是什么？ 重定

位值转移目标地址=PC+偏移地址，PC=0x8048380+0x07-init–	PC=0x8048380+0x07-(-4)=0x804838b–	重定位值=转移目标地址-PC=0048394-0x804838b=0x9call指令的机器代码为“e8 09 00 00 00”

值为-4

PC相对地址方式下，重定位值计算公式为： ADDR(r_sym) – ( ( ADDR(.text) + r_offset ) – init )

call指令下条指令地址

引用目标处

即当前PC的值

S KIP

## 第 80 页

确定定义符号的地址

%esp

brk

0xC00000000

0x08048000

内核虚存区

共享库区域

堆（heap） 动态生成)

用户栈 动态生成

未使用

读写数据段(.data, .bss)

只读代码段(.text, .rodata等)

从可 执行 文件 装入

1GB

int buf[2]={1,2}

可执行目标文件Headers

main()

swap()

int *bufp0=&buf[0]

更多系统代码

系统数据

.text

.symtab.debug

.data

int *bufp1

.bss

系统代码

BACK

## 第 81 页

R_386_32的重定位方式

buf定义在.data  节中偏移为0处， 占8B，没有需重 定位的符号。

Disassembly of section .data:00000000 <buf>:0:	01 00 00 00 02 00 00 00

main.o中.data和.rel.data节内容

int buf[2]={1,2};int main()……

main.c

extern int buf[];int *bufp0 = &buf[0];  static int *bufp1;void swap()……

swap.c

Disassembly of section .data:00000000 <bufp0>:0:	00 00 00 00

0：R_386_32	buf

swap.o中.data和.rel.data节内容

bufp0定义 在.data节中 偏移为0处， 占4B，初值 为0x0

重定位节.rel.data中有一个重定位表项：r_offset=0x0,  r_sym=9, r_type=R_386_32，OBJDUMP工具解释后显示为

“0：R_386_32 buf”

r_sym=9说明引用的是buf！

## 第 82 页

swap.o中的符号表

swap.o中的符号表中最后4个条目

buf是swap.o的符号表中第9项，是未定义符号，类型和大小未 知，并是全局符号，故在其他模块中定义。重定位节.rel.data中有一个重定位表项：r_offset=0x0,  r_sym=9, r_type=R_386_32，OBJDUMP工具解释后显示为 “0：R_386_32 buf”r_sym=9说明引用的是buf！

## 第 83 页

R_386_32的重定位方式

8049620:08049628 <bufp0>:8049628:

01 00 00 00 02 00 00 0020 96 04 08

假定：buf在运行时的存储地址ADDR(buf)=0x8049620则重定位后，bufp0的地址及内容变为什么？buf和bufp0同属于.data节，故在可执行文件中它们被合并–	bufp0紧接在buf后，故地址为0x8049620+8= 0x8049628因是R_386_32方式，故bufp0内容为buf的绝对地址  0x8049620，即“20 96 04 08”可执行目标文件中.data节的内容Disassembly of section .data:08049620 <buf>:

## 第 84 页

swap.c

extern int buf[];int *bufp0 = &buf[0];  static int *bufp1;void swap(){int temp;bufp1 = &buf[1];  temp = *bufp0;*bufp0 = *bufp1;*bufp1 = temp;}

Disassembly of section .text:

swap.o重定位 00000000 <swap>:

0:	551:	89 e53:	83 ec 10

push	%ebpmov	%esp,%ebp  sub	$0x10,%esp

6:	c7 05 0 0 00 00 00 04 movl	$0x4,0x0d:	00 00 00

8: R_386_32  c: R_386_32

.bss  buf

10:	a1 00 00 00 00	mov

0x0,%eax

11: R_386_32

bufp0

(%eax),%eax

%eax,-0x4(%ebp)

15:	8b 00	mov17:	89 45 fc	mov  1a:	a1 00 00 00 00 	 mov

0x0,%eax

1b: R_386_32

bufp0

1f:	8b 15 00 00 00 00mov

0x0,%edx

21: R_386_32

.bss

(%edx),%edx

25:	8b 12	mov27:	89 10	mov29:	a1 00 00 00 00	mov

%edx,(%eax)  0x0,%eax

2a: R_386_32	.bss

-0x4(%ebp),%edx

2e:	8b 55 fc  31:	89 10

movmov	%edx,(%eax)

33:	c934:	c3

leave  ret

共有6处需要重定位划红线处：8、c、  11、1b、21、2a

## 第 85 页

swap.o重定位

bufp1 = &buf[1];  temp = *bufp0;*bufp0 = *bufp1;*bufp1 = temp;

6:	c7 05 00 00 00 00 04 movl	$0x4,0x0d:	00 00 00

8: R_386_32  c: R_386_32

.bss  buf

10:	a1 00 00 00 00 	mov

0x0,%eax

11: R_386_32

bufp0

(%eax),%eax

%eax,-0x4(%ebp)

15:	8b 00	mov17:	89 45 fc	mov  1a:	a1 00 00 00 00	 mov

0x0,%eax

1b: R_386_32	bufp0  1f:	8b 15 00 00 00 00mov	0x0,%edx

21: R_386_32	.bss

(%edx),%edx

25:	8b 12	mov27:	89 10	mov29:	a1  00 00 00 00	mov

%edx,(%eax)  0x0,%eax

2a: R_386_32	.bss

-0x4(%ebp),%edx

2e:	8b 55 fc  31:	89 10

movmov	%edx,(%eax)

8 (bufp1)：00 97 04 08c (&buf[1])：24 96 04 0811 (bufp0)：28 96 04 081b (bufp0) : 28 96 04 0821 (bufp1)：00 97 04 082a (bufp1)：00 97 04 08

buf和bufp0的地址分别是0x8049620和0x8049628  &buf[1](c处重定位值）为0x8049620+0x4=0x8049624bufp1的地址就是链接合并后.bss节的首地址，假定为0x8049700

## 第 86 页

08048380 <main>:

e8 09 00 00 00	call	8048394 <swap>  b8 00 00 00 00		mov		$0x0,%eax

8048386:804838b:8048390:	c98048391:	c3

8048392:	908048393:	90

leaveret  nop  nop

重定位后

08048394 <swap>:

push %ebp

5589 e583 ec 10

mov	%esp,%ebp  sub	$0x10,%esp

8048394:8048395:8048397:804839a:80483a1:

c7 05 00 97 04 08 24 mov $0x8049624,0x804970096 04 08

假定每个函数 要求4字节边界 对齐,故填充两 条nop指令

你能写出该call指令 的功能描述吗？

R[eip]=0x804838bR[esp]← R[esp]-4M[R[esp]] ←R[eip]R[eip] ←R[eip]+0x9

## 第 87 页

共享库和动态链接

## 第 88 页

动态链接的共享库（Shared Libraries）

静态库有一些缺点：库函数（如printf）被包含在每个运行进程的代码段中，对于并发 运行上百个进程的系统，造成极大的主存资源浪费库函数（如printf）被合并在可执行目标中，磁盘上存放着数千个 可执行文件，造成磁盘空间的极大浪费程序员需关注是否有函数库的新版本出现，并须定期下载、重新编 译和链接，更新困难、使用不便解决方案: Shared Libraries （共享库）是一个目标文件，包含有代码和数据从程序中分离出来，磁盘和内存中都只有一个备份可以动态地在装入时或运行时被加载并链接Window称其为动态链接库（Dynamic Link Libraries，.dll文件）Linux称其为动态共享对象（ Dynamic Shared Objects, .so文件）

## 第 89 页

共享库（Shared Libraries）

动态链接可以按以下两种方式进行：在第一次加载并运行时进行 (load-time linking).Linux通常由动态链接器(ld-linux.so)自动处理标准C库 (libc.so) 通常按这种方式动态被链接在已经开始运行后进行(run-time linking).在Linux中，通过调用 dlopen()等接口来实现共享模块在内存中只有一个备份，被所有进程共享，节省内存空间 共享库文件在磁盘中只有一个备份，被所有程序共享链接，节省磁盘空间共享库升级时，被自动加载到内存和程序动态链接，使用方便 共享库可分模块、独立、用不同编程语言进行开发，效率高 第三方开发的共享库可作为程序插件，使程序功能易于扩展

## 第 90 页

自定义一个动态共享库文件

gcc –c myproc1.c myproc2.c

gcc –shared –fPIC –o mylib.so myproc1.o myproc2.o

myproc1.c# include <stdio.h>  void myfunc1(){printf("%s","This is myfunc1!\n");}myproc2.c# include <stdio.h>  void myfunc2(){printf("%s","This is myfunc2\n");}

位置无关的共享代码库文件

PIC：Position Independent Code位置无关代码1）保证共享库代码的 位置可以是不确定的

2）即使共享库代码的 长度发生变化，也不会 影响调用它的程序

## 第 91 页

加载时动态链接

gcc –c main.c

gcc –o myproc main.o ./mylib.so调用关系：main→myfunc1→printf  main.cvoid myfunc1(viod);  int main(){myfunc1();  return 0;}

libc.so无需明显指出

加载 myproc 时，加载器发现在其程 序头表中有 .interp 段，其中包含了 动态链接器路径名 ld-linux.so，因 而加载器根据指定路径加载并启动动 态链接器运行。动态链接器完成相应 的重定位工作后，再把控制权交给 myproc，启动其第一条指令执行。

SKIP

## 第 92 页

加载时动态链接

程序头表中有一个特殊的段：INTERP其中记录了动态链接器目录及文件名ld-linux.so

BACK

## 第 93 页

运行时动态链#include <stdio.h>

#include <dlfcn.h>

int main(){void *handle;void (*myfunc1)();  char *error;/* 动态装入包含函数myfunc1()的共享库文件 */handle = dlopen("./mylib.so", RTLD_LAZY);  if (!handle) {fprintf(stderr, "%s\n", dlerror());exit(1);}/* 获得一个指向函数myfunc1()的指针myfunc1*/  myfunc1 = dlsym(handle, "myfunc1");if ((error = dlerror()) != NULL) {fprintf(stderr, "%s\n", error);  exit(1);}/* 现在可以像调用其他函数一样调用函数myfunc1() */  myfunc1();/* 关闭（卸载）共享库文件 */if (dlclose(handle) < 0) {  fprintf(stderr, "%s\n", dlerror());  exit(1);}return 0;}

可通过动态链接器接 口提供的函数在运行 时进行动态链接类UNIX系统中的动 态链接器接口定义了 相应的函数，如 dlopen, dlsym,  dlerror, dlclose等，  其头文件为dlfcn.h

## 第 94 页

位置无关代码（PIC）

动态链接用到一个重要概念：–	位置无关代码（Position-Independent Code，PIC

–	GCC选项-fPIC指示生成PIC代码共享库代码是一种PIC–	共享库代码的位置可以是不确定的

–	即使共享库代码的长度发生变化，也不影响调用它的程序引入PIC的目的–	链接器无需修改代码即可将共享库加载到任意地址运行所有引用情况模块内的过程调用、跳转，采用PC相对偏移寻址模块内数据访问，如模块内的全局变量和静态变量

模块外的过程调用、跳转模块外的数据访问，如外部变量的访问

要实现动态链接， 必须生成PIC代码

要生成PIC代码，主 要解决这两个问题

## 第 95 页

(1) 模块内部函数调用或跳转

调用或跳转源与目的地都在同一个模块，相对 位置固定，只要用相对偏移寻址即可无需动态链接器进行重定位

static int a;  static int b;extern	void ext();void bar(){a=1;  b=2;}void foo(){bar();ext();}

8048344 <bar>:8048344:	55

8048345:	89 e5……8048352:	c38048353:	90

pushl	%ebpmovl	%esp, %ebpret  nop

8048354	<foo>:8048354:	55……

e8 db ff ff ff

pushl %ebpcall 8048344 <bar>

8048364:8048369:……

call的目标地址为：  0x8048369+0xffffffdb(-0x25)=  0x8048344JMP指令也可用相 对寻址方式解决

## 第 96 页

(2) 模块内部数据引用

.data节与.text节之间的相对位置确定，任何引用局 部符号的指令与该符号之间的距离是一个常数

static	int a;

extern int b;

extern	void ext();  void bar(){a=1;  b=2;}…….

0000344 <bar>:0000344:	55

89 e5

pushl	%ebpmovl	%esp, %ebp

e8 50 00 00 00	call	39c < 	get_pc>81 c1 8c 11 00 00 addl	$0x118c, %ecx

c7 81 28 00 00 00 movl $0x1, 0x28(%ecx)

ret

0000345:0000347:000034c:0000352:……  0000362:000039c <000039c:000039f:

c3get_pc>:  8b 0c 24  c3

movl	(%esp), %ecx  ret

变量a与引用a的指令之间的距离为常数，调用 	get_pc后，call指令的返回地 址被置ECX。若模块被加载到0x9000000，则a的访问地址为：0x9000000+0x34c+0x118c(指令与.data间距离)+0x28(a在.data节中偏移)

.text

.data

0x118c+0x28

多用了4条指令

## 第 97 页

(3) 模块外数据的引用

引用其他模块的全局变量，无法确定相对距离在.data节开始处设置一个指针数组（全局偏移表，  GOT），指针可指向一个全局变量GOT与引用数据的指令之间相对距离固定

static	int a;

extern int b;

extern	void ext();  void bar(){a=1;  b=2;}……

pushl	%ebp

00000344 <bar>:00000344:	55……

e8 00 00 00 00

call	0000035c  popl		%ebx

addl	$1180, %ebx

movl	(%ebx), %eax

movl	$2, (%eax)

00000357:0000035c:	5b000035d:………………

PIC有两个缺陷：多用4条指令；多了GOT（Global Offset  Table），故需多用一个寄存器（如EBX），易造成寄存器溢出

编译器为GOT每一项生成一个重定位项（如.rel节…）加载时，动态链接器对GOT中各项进行重定位，填入 所引用的地址（如&b）

0x1180

.text

&bGOT.data

.textb .data共享库模块

## 第 98 页

(4) 模块间调用、跳转

方法一：类似于(3)，在GOT中加一个项(指针)，用 于指向目标函数的首地址（如&ext）动态加载时，填入目标函数的首地址

static	int a;

extern int b;

extern	void ext();  void foo(){bar();ext();}……

pushl	%ebp

0000050c <foo>:0000050c:	55……

…………

多用三条指令并额外多用一个寄存器（如EBX）可用“延迟绑定（lazy binding）”技术减少指令条数：  不在加载时重定位，而延迟到第一次函数调用时，需要用 GOT和PLT（Procedure linkage Table, 过程链接表）

call	*(%ebx)*(%ebx)为间接地址：R[eip]←M[R[ebx]]

0x1204

.text

&b GOT&ext

.data

.text

b .data

ext

共享库模块

## 第 99 页

方法二：延迟绑定GOT是.data节一部分，开始三项固定，含义如下：  GOT[0]为.dynamic节首址，该节中包含动态链接器所需要

的基本信息，如符号表位置、重定位表位置等；  GOT[1]为动态链接器的标识信息GOT[2]为动态链接器延迟绑定代码的入口地址调用的共享库函数都有GOT项，如GOT[3]对应ext

PLT是.text节一部分，结构数组，每项16B，除PLT[0] 外，其余项各对应一个共享库函数，如PLT[1]对应extPLT[0]

0804833c:	ff 35 88 95 04 08	pushl	0x80495888048342:	ff 25 8c 95 04 08	jmp	*0x804958c8048348:	00 00 00 00

PLT[1] <ext>	用 ID=0 标识ext()函数

0804834c:	ff 25 90 95 04 08	jmp	*0x8049590

pushl		$0x0  jmp	804833c

(4) 模块间调用、跳转

extern	void ext();  void foo() {bar();ext();}……

8048352:	68 00 00 00 008048357:	e9 e0	ff	ff	ffext() 的 调 用 指 令 ：  804845b:	e8 ec fe ff ff

call	804834c <ext>

延时绑定代码根据GOT[1]和ID确

定ext地址填入GOT[3]，并转ext

执行，以后调用ext，只要多执行

一条jmp指令而不是多3条指令。

80495848049588804958c8049590

804833c804834c

