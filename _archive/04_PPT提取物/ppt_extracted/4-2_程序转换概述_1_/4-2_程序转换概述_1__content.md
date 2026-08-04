# 4-2_程序转换概述_1_

- 幻灯片总数: 90
- 提取时间: 2026-06-15

---

## 第 1 页

程序的转换及机器级表示

陈盛德人工智能与低空技术学院email: shengde-chen@scau.edu.cn

## 第 2 页

过程调用的机器级表示

## 第 3 页

int add ( int x, int y ) {

return x+y;

int main ( ) {       int t1 = 125;

int t2 = 80;

int sum = add (t1, t2);  return sum;

过程调用的机器级表示

以下过程（函数）调用对应的机器级代码是什么？如何将实参t1(125)、t2(80)分别传递给add中的形式参数x、yadd函数执行的结果如何返回给caller?

addmain

main：

add：

存放参数调出add执行

取出参数 执行存返回结果

返回main参数通过栈（stack）来传递！ 栈（stack）在哪里？

## 第 4 页

可执行文件的存储器映像

ESP(栈顶)

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

从高地 址向低 地址增 长！

## 第 5 页

过程调用的机器级表示

（6）Q取出返回地址，将控制转移到P。RET指令

结束阶段

准备阶段

Q过程

P过程

过程调用的执行步骤(P为调用者，Q为被调用者)P将入口参数（实参）放到Q能访问到的地方；P保存返回地址，然后将控制转移到Q；CALL指令Q保存P的现场，并为自己的非静态局部变量分配空间；执行Q的过程体（函数体）；	处理阶段Q恢复P的现场，释放局部变量空间；

main：	add：

存放参数调出add执行

取出参数 执行存返回结果

返回main

何为现场？通用寄存器的内容！ 为何要保存现场？因为所有过程共享一套通用寄存器

## 第 6 页

过程调用的机器级表示

IA-32的寄存器使用约定–	调用者保存寄存器：EAX、EDX、ECX

当过程P调用过程Q时，Q可以直接使用这三个寄存器，不用 将它们的值保存到栈中。如果P在从Q返回后还要用这三个寄 存器的话，P应在转到Q之前先保存，并在从Q返回后先恢复 它们的值再使用。被调用者保存寄存器：EBX、ESI、EDIQ必须先将它们的值保存到栈中再使用它们，并在返回P之前 恢复它们的值。EBP和ESP分别是帧指针寄存器和栈指针寄存器，分别用来指 向当前栈帧的底部和顶部。问题：为减少准备和结束阶段的开销，每个过程应先使用哪些寄存器？  EAX、ECX、EDX！

想象一下，共用同一 套盘子做菜的情况！

## 第 7 页

过程调用的机器级表示

IA-32的栈、栈帧–	IA-32使用栈来支持过程的嵌套调用

过程的入口参数、返回地址、被保存寄存器的值、被调用过程中的非静态局部变量等都会被压入栈中栈从高地址向低地址增长

–  每个过程都有自己的栈区，这个栈区称为栈帧

一个栈由若干栈帧组成   每个栈帧用专门的帧指针寄存器EBP指定起始位置   当前栈帧的范围在帧指针EBP和栈指针ESP指向区域之间   在一个过程内对栈中信息的访问大多通过帧指针EBP进行

## 第 8 页

过程调用的机器级表示

过程调用过程中栈和栈帧的变化 (P为调用过程、Q为被调用过程)

④③

Q(参数1，…，参数n);

再来看看栈 在哪里？

## 第 9 页

一个简

单的

过程调用例子

%ebp%esp, %ebp$24, %esp

add

%eax, -4(%ebp)

caller：  pushl  movl  subl  movl  movl  movl  movl  movl  movl  call  movl  movl  leave  ret

准备 阶段

-4(%ebp), %eax结束 阶段

caller 	帧底

int add ( int x, int y ) {  return x+y;}int caller ( ) {int	t1 = 125;

int	t2 = 80;int	sum = add (t1, t2);  return sum;

ESP+4

$125, -12(%ebp)	分配局$80, -8(%ebp)	部变量-8(%ebp), %eax%eax, 4(%esp)	准备入-12(%ebp), %eax	口参数%eax, (%esp)

-4-8

-12-16

-20

返回参数总在EAX中

add函数开始是什么？  pushl	%ebpmovl	%esp, %ebp

add

caller

准备返 回参数movl %ebp, %esppopl %ebp

## 第 10 页

过程（函数）的结构

一个C过程的大致结构如下：准备阶段形成帧底：push指令 和 mov指令生成栈帧（如果需要的话）：sub指令保存现场（如果有被调用者保存寄存器） ：mov指令过程（函数）体分配局部变量空间，并赋值具体处理逻辑，如果遇到函数调用时准备参数：将实参送栈帧入口参数处CALL指令：保存返回地址并转被调用函数在EAX中准备返回参数结束阶段退栈：leave指令 或 pop指令取返回地址返回：ret指令

## 第 11 页

入口参数的位置

返回地址

EBP在main中的值

EBP

入口参数1

入口参数2

入口参数3

EBP+16  EBP+12  EBP+8

movl	参数1, (%esp)

movl	参数3，8(%esp)	准备………..	入口参数

call	add

R[esp]←R[esp]-4  M[R[esp]]←返回地址 R[eip]←add函数首地址

返回地址是什么？call指令的下一条指令的地址！IA-32中，若参数类型是 unsigned char、char或 unsigned short、short，  也都分配4个字节故在被调用函数中，使用 R[ebp]+8、R[ebp]+12、 R[ebp]+16作为有效地址来 访问函数的入口参数每个过程开始两条指令  pushl %ebpmovl %esp, %ebp

IA-32规定

## 第 12 页

过程调用参数传递举例

程序一的输出：  a=15	b=22  a=22	b=15

程序二的输出：  a=15	b=22  a=15	b=22

程序一#include <stdio.h>  main ( ){int a=15, b=22;printf (“a=%d\tb=%d\n”, a, b);  swap (&a, &b);printf (“a=%d\tb=%d\n”, a, b);}swap (int *x, int *y ){int t=*x;

*x=*y;*y=t;

x=y;  y=t;

程序二#include <stdio.h>  main ( ){int a=15, b=22;printf (“a=%d\tb=%d\n”, a, b);  swap (a, b);printf (“a=%d\tb=%d\n”, a, b);}swap (int x, int y ){int t=x;按值传递参数

按地址传递参数执行结果？为什么？

## 第 13 页

过程调用参数传递举例

EBP在main中的值

EBP

EBP+12EBP+8返回地址

EBX在main中的值

R[ecx]←M[&a]=15R[ebx]←M[&b]=22  M[&a] ← R[ebx] =22  M[&b] ← R[ecx] = 15

22

15

局部变量a和b 进行了交换

装入有效地址

## 第 14 页

过程调用参数传递举例

返回地址

EBP在main中的值

EBP

EBP+12EBP+8

R[edx]←15  R[eax]←22

22

15

M[R[ebp]+8] ← R[eax] =22  M[R[ebp]+12] ← R[edx] =15

局部变量a和b没有交换， 交换的仅是入口参数

## 第 15 页

过程调用

1	void test ( int x, int *ptr )

2	{3	if	( x>0 && *ptr>0 )  4	*ptr+=x;

5	}

7	void caller (int a, int y )  8	{

int x = a>0 ? a : a+100;

910		test (x, &y)；  11	}

test

caller

6	100	200

调用caller的过程为P，P中给出形参a和y的 实参分别是100和200，画出相应栈帧中的状态test的形参是按值传递还是按地址传递？test的形参ptr对应的实参是一个 什么类型的值？	前者按值、后者按地址。一定是一个地址test中被改变的*ptr的结果如何返回给它的调用过程caller？caller中被改变的y的结果能否返回给过程P？为什么？

进入test并生成其栈帧 后，栈中状态如何？，并回答下列问题。

执行Caller之前

## 第 16 页

过程调用

1	void test ( int x, int *ptr )

2	{3	if	( x>0 && *ptr>0 )  4	*ptr+=x;

5	}

7	void caller (int a, int y )  8	{

int x = a>0 ? a : a+100;

910		test (x, &y)；  11	}

，并回答下列问题。

caller

6	100	200

调用caller的过程为P，P中给出形参a和y的 实参分别是100和200，画出相应栈帧中的状态test的形参是按值传递还是按地址传递？test的形参ptr对应的实参是一个 什么类型的值？	前者按值、后者按地址。一定是一个地址test中被改变的*ptr的结果如何返回给它的调用过程caller？第10行执行后，P帧中200变成300，test退帧后，caller中通过y引用该值300caller中被改变的y的结果能否返回给过程P？为什么？第11行执行后caller退帧并返回P，因P中无变量与之对应，故无法引用该值300

执行test之前

## 第 17 页

过程调用

1	void test ( int x, int *ptr )

2	{3	if	( x>0 && *ptr>0 )  4	*ptr+=x;

5	}

7	void caller (int a, int y )  8	{

int x = a>0 ? a : a+100;

910		test (x, &y)；  11	}

举例

进入test并生成其栈帧 后，栈中状态如何？，并回答下列问题。

&y:

&a:

6	100	200

300

调用caller的过程为P，P中给出形参a和y的 实参分别是100和200，画出相应栈帧中的状态test的形参是按值传递还是按地址传递？test的形参ptr对应的实参是一个 什么类型的值？	前者按值、后者按地址。一定是一个地址test中被改变的*ptr的结果如何返回给它的调用过程caller？第10行执行后，P帧中200变成300，test退帧后，caller中通过y引用该值300caller中被改变的y的结果能否返回给过程P？为什么？第11行执行后caller退帧并返回P，因P中无变量与之对应，故无法引用该值300

test过程返回前

## 第 18 页

递归过程调用举

nn_sum(n-1)

nn_sum(n)

int	nn_sum ( int n){int result;  if	(n<=0 )result=0;  elseresult=n+nn_sum(n-1);	P  return	result；}

Sum(n)

Sum(n-1)

R[ebx]←n  R[eax]←0if (n≤0）转L2R[eax]←n-1

R[eax] ← 0+1+2+…+(n-1)+n

每次递归调用都会 增加一个栈帧，所 以空间开销很大。

## 第 19 页

过程调用的机器级表示

递归函数nn_sum的执行流程

过程功能由过程体实现，为支持过程调用，每个过程包含准备阶段和结束阶段。因而 每增加一次过程调用，就要增加许多条包含在准备阶段和结束阶段的额外指令，它们 对程序性能影响很大，应尽量避免不必要的过程调用，特别是递归调用。

## 第 20 页

选择和循环语句的机器级表示

## 第 21 页

选择结构的机器级表示

if ~ else语句的机器级表示

if (cond_expr)  then_statementelseelse_statement

红框处为条件转移指令！  篮框处为无条件转移指令！

## 第 22 页

If-else语句举例

int	get_cont( int *p1, int *p2 ) {if	( p1 > p2 )return *p2;elsereturn *p1;}

p1和p2对应实参的存储地址分别为 R[ebp]+8、R[ebp]+12，EBP指 向当前栈帧底部，结果存放在EAX。

SKIP

## 第 23 页

入口参数的位置

返回地址

EBP在main中的值

EBP

入口参数1

入口参数2

入口参数3

EBP+16  EBP+12  EBP+8

call	add

movl	参数3，8(%esp)	准备………..	入口movl	参数1, (%esp)	参数

R[esp]←R[esp]-4  M[R[esp]]←返回地址 R[eip]←add函数首地址

返回地址是什么？call指令的下一条指令的地址！IA-32中，若参数类型是 unsigned char、char或 unsigned short、short，  也都分配4个字节故在被调用函数中，使用 R[ebp]+8、R[ebp]+12、 R[ebp]+16作为有效地址来 访问函数的入口参数每个过程开始两条指令  pushl %ebpmovl %esp, %ebpBACK

## 第 24 页

switch-case语句举例

int sw_test(int a, int b, int c){int result;  switch(a) {  case 15:c=b&0x0f;  case 10:result=c+50;  break;case 12:case 17:result=b+50;  break;case 14:result=b  break;default:result=a;}return result;}

跳转表在目标文件 的只读节中，按4  字节边界对齐。

R[eax]=a-10=iif (a-10)>7 转 L5  转.L8+4*i 处的地址

a=1011121314151617

## 第 25 页

循环结构的机器级表示

do~while循环的机器级表示

do	loop_body_statement  while (cond_expr);loop：loop_body_statement  c=cond_expr;if (c) goto loop;while循环的机器级表示while (cond_expr)  loop_body_statementc=cond_expr;if (!c) goto done;  loop：loop_body_statement  c=cond_expr;if (c) goto loop;  done：

for循环的机器级表示for (begin_expr; cond_expr; update_expr)  loop_body_statement

begin_expr;  c=cond_expr;if (!c) goto done;  loop：loop_body_statement  update_expr;  c=cond_expr;if (c) goto loop;  done：

红色处为条件转移指令！

## 第 26 页

循环结构与递归的比较

递归函数nn_sum仅为说明原理，实际上可直接用公式，为说明循环的

机器级表示，这里用循环实现。int	nn_sum ( int n){int i;int result=0;for (i=1; i <=n; i++)  result+=i;return result；}

movl	8(%ebp), %ecx  movl	$0, %eax

movl	$1, %edx  cmpl	%ecx, %edx

jg	.L2.L1:

addl	%edx, %eax

addl	$1, %edx

cmpl	%ecx, %edx

jle	.L1

.L2

过程体中没用到被调用过程保存寄存器。因而，该过程栈帧中仅需保留EBP， 即其栈帧仅占用4字节空间，若考虑栈帧按16B对齐，也仅用16字节，而递归方 式则用了16n字节，是n倍关系！每次递归调用都要执行16条指令，一共多 了n次过程调用，因而，递归方式比循环方式至少多执行16n条指令。由此看 出，为提高程序性能，能用非递归方式执行则最好用非递归方式。

i 和 result 分别分 配在EDX和EAX中。通常复杂局部变量 被分配在栈中，而 这里都是简单变量

SKIP

## 第 27 页

递归过程调用举例

int	nn_sum ( int n){int result;  if	(n<=0 )result=0;elseresult=n+nn_sum(n-1);  return	result；}

Sum(n)

Sum(n-1)

BACK时间开销：每次递归执行16条指令，共16n条指令 空间开销：一次调用增加16B栈帧，共16n

P的栈帧

## 第 28 页

逆向工程举例

movl	8(%ebp), %ebx  movl	$0, %eaxmovl	$0, %ecx.L12:leal	(%eax,%eax), %edx  movl	%ebx, %eaxandl	$1, %eax  orl	%edx, %eaxshrl	%ebx  addl	$1, %ecx  cmpljne

$32, %ecx.L12

① 处为i=0，② 处为i≠32，③ 处为i++。入口参数 x 在EBX中，返回参数 result 在EAX中。LEA实现“2*result”，  即：将result左移一位；第6和第7条指令则实现“x&0x01”；第8条指令实 现“result=(result<<1) | (x & 0x01)”，第9条指令实现“x>>=1”。综 上所述，④ 处的C语言语句是：“result=(result<<1) | (x & 0x01); x>>=1;”。

int function_test( unsigned x){int result=0;  int i；for ( 	①	; 	②	; 	③	) { 	④	；}return result;}

## 第 29 页

数组和指针类型的分配和访问

## 第 30 页

数组的分配和访问

数组元素在内存（存储器）的存放和访问例如，定义一个具有4个元素的静态存储型 short 数据 类型数组A，可以写成“static short A[4];”第 i（0≤i≤3）个元素的地址计算公式为&A[0]+2*i。假定数组A的首地址存放在EDX中，i 存放在ECX中，  现要将A[i]取到AX中，则所用的汇编指令是什么？

movw	(%edx, %ecx, 2), %ax

其中，ECX为变址（索引）寄存器，在循环体中增量，

比例因子是2！

数组可以将同类基本类型数据组合起来形成一个大的数据集合数组不可能放在寄存器中或作为立即数存放在指令中一定被分配在存储器中，且连续存放

## 第 31 页

数组的分配和访问

填写下表

## 第 32 页

数组的分配和访问

填写下表

## 第 33 页

数组元素在内存的存放和访问

分配在静态区的数组的初始化和访问

假定 i 被分配在ECX中，sum被分配在EAX中，则 “sum+=buf[i];”和 i++ 可用什么指令实现？addl (%edx , %ecx, 4), %eax  addl	$1，%ecx

buf是在静态区分配的数组，链接后，buf  在可执行目标文件的数据段中分配了空间08049080 <buf>：08049080：	0A 00 00 00 14 00 00 00此时，buf=&buf[0]=0x08049080编译器通常将其先存放到寄存器(如EDX)中

int buf[2] = {10, 20};  int main ( ){int i, sum=0;for (i=0; i<2; i++)  sum+=buf[i];return sum;}

## 第 34 页

数组元素在内存的存放和访问

auto型数组的初始化和访问

分配在栈中， 故数组首址通 过EBP来定位

movl $10, -8(%ebp)  movl $20, -4(%ebp)

//buf[0]的地址为R[ebp]-8，将10赋给buf[0]//buf[1]的地址为R[ebp]-4，将20赋给buf[1]

对buf进行初始化的指令是什么？

若将buf首址放到EDX中，则获得buf首址的对应指令是什么？leal -8(%ebp), %edx	//buf[0]的地址为R[ebp]-8，将buf首址送EDX

int adder ( ){int buf[2] = {10, 20};  int i, sum=0;for (i=0; i<2; i++)sum+=buf[i];

return sum;

-4-8

## 第 35 页

数组元素在内存的存放和访问

指针数组和多维数组由若干指向同类目标的指针变量组成的数组称为指针数组。其定义的一般形式如下：存储类型 数据类型 *指针数组名[元素个数]；例如，“int *a[10];”定义了一个指针数组a，它有10个元 素，每个元素都是一个指向int型数据的指针。一个指针数组可以实现一个二维数组。a[0]a[1]

a[9]

## 第 36 页

## 第 37 页

结构和联合数据类型的分配和访问

## 第 38 页

结构体数据的分配和访问

结构体成员在内存的存放和访问分配在栈中的auto结构型变量的首地址由EBP或ESP来定位分配在静态区的结构型变量首地址是一个确定的静态区地址结构型变量 x 各成员首址可用“基址加偏移量”的寻址方式

若变量x分配在地址0x8049200开始的区域，那么  x=&(x.id)=0x8049200（ 若 x 在 EDX 中 ）  &(x.name)= 0x8049200+8=0x8049208

&(x.post)= 0x8049200+8+12=0x8049214

&(x.phone)=0x8049200+8+12+4+100=0x804927C

struct cont_info {char id[8];char name [12];

unsigned post;

char address[100];	&(x.address)=0x8049200+8+12+4=0x8049218

char phone[20];

};struct cont_info x={“0000000”, “ZhangS”, 210022, “273 longstreet, High Building #3015”, “12345678”}；x初始化后，在地址0x8049208到0x804920D处是字符串“ZhangS”，  0x804920E处是字符‘\0’，从0x804920F到0x8049213处都是空字符。“unsigned xpost=x.post;”对应汇编指令为“movl 20(%edx), %eax”

## 第 39 页

联合体数据的分配和访问

联合体各成员共享存储空间，按最大长度成员所需空间大小为目标union uarea {

char	c_data;  short s_data;

int	i_data;  long	 l_data;

IA-32中编译时，long和int长度一样，故 uarea所占空间为4个字节。而对于与uarea  有相同成员的结构型变量来说，其占用空间 大小至少有11个字节，对齐的话则占用更多。

};通常用于特殊场合，如，当事先知道某种数据结构中的不同字段的使用时间是互斥的，就可将这些字段声明为联合，以减少空间。但有时会得不偿失，可能只会减少少量空间却大大增加处理复杂性。

## 第 40 页

## 第 41 页

数据的对齐存放

## 第 42 页

数据的对齐

对齐: 要求数据的地址是相应的边界地址目前机器字长为32位或64位，主存按一个传送单位（32/64/128位）进 行存取，而按字节编址，例如：若传送单位为32位，则每次最多读写32位，即：第0~3字节同时读写，第4~7字节同时读写，……，以此类推。按 边界对齐，可使读写数据位于4i~4i+3(i=0,1,2,…) 单元指令系统支持对字节、半字、字及双字的运算各种不同长度的数据存放时，有两种处理方式:按边界对齐（若一个字为32位）字地址：4的倍数(低两位为0)半字地址：2的倍数(低位为0)字节地址：任意不按边界对齐坏处：可能会增加访存次数！

## 第 43 页

0004081216

0	1	2	3

边界不对齐	00

1216

对齐(Alignment)

如：int i, short k, double x, char c, short j,……

则：&i=0; &k=4; &x=8; &c=16; &j=18;……0	1	2	3

则： &i=0; &k=4; &x=6; &c=14; &j=15;……

04x：3个周期	08

j：2个周期

按边界对齐x：2个周期  j：1个周期

虽节省了空间，但 增加了访存次数！需要权衡，目前来 看，浪费一点存储 空间没有关系！

若1个字=32位， 主存每次最多存 取一个字，按字 节编址，则每次 只能读写某个字 地址开始的4个单 元中连续的1、2、3或4个字节

## 第 44 页

数据的对齐

最简单的对齐策略是：按其数据长度进行对齐。例如，Windows采用策略：int型地址是4的倍数，short型地址是2  的倍数，double和long long型的是8的倍数，float型的是4  的倍数，char不对齐Linux采用更宽松策略：short型是2的倍数，其他类型如int、  float、double和指针等都是4的倍数

只要SD首址按4B  边界对齐，所有字 段都能按要求对齐

结构变量首 地址按4字 节边界对齐

结构数组变量的 最末可能需要插 空，以使每个数 组元素都按4字节 边界对齐

struct SDT {

int	i;

short	si;

double d;

char	c;} sa[10];

struct SD {

int	i;short	si;

char	c;

double	d;

};

## 第 45 页

对齐(Alignment)举例

例如，考虑下列两个结构声明：  struct	S1 {

int i；  char c；  int j；

}；

struct	S2 {int	i；int	j；  char	c；}；

在要求对齐的情况下，哪种结构声明更好？

S1：

X  X	X

S2：	j

4c4

8c

需要12个字节

只需要9个字节

S2：

X  X	X

0	4

8c

对于“struct S2 d[4]”，只分配9个字节能否满足对齐要求？ 不能！

也需要12个字节

S2比S1好

## 第 46 页

对齐方式的设定

#pragma pack(n)为编译器指定结构体或类内部的成员变量的对齐方式。当自然边界（如int型按4字节、short型按2字节、float按4字节）比n大时，按n字节对齐。否则，按自然边界对齐。 	attribute 	((aligned(m)))为编译器指定一个结构体或类或联合体或一个单独的变量(对象)的 对齐方式。按m字节对齐(m必须是2的幂次方)，且其占用空间大小也是m的 整数倍，以保证在申请连续存储空间时各元素也按m字节对齐。 	attribute 	((packed))不按边界对齐，称为紧凑方式。

## 第 47 页

对齐方式的设定

#include<stdio.h>  #pragma pack(4)  typedef struct {

uint32_t f1;  uint8_t     f2;uint8_t f3;  uint32_t f4;  uint64_t   f5;

} 	attribute 	((aligned(1024))) ts;  int main(){printf("Struct size is: %d, aligned on 1024\n",sizeof(ts));  printf("Allocate f1 on address: 0x%x\n",&(((ts*)0)->f1));  printf("Allocate f2 on address: 0x%x\n",&(((ts*)0)->f2));  printf("Allocate f3 on address: 0x%x\n",&(((ts*)0)->f3));  printf("Allocate f4 on address: 0x%x\n",&(((ts*)0)->f4));  printf("Allocate f5 on address: 0x%x\n",&(((ts*)0)->f5));  return 0;}

输出：Struct size is: 1024, aligned on 1024  Allocate f1 on address: 0x0Allocate f2 on address: 0x4  Allocate f3 on address: 0x5  Allocate f4 on address: 0x8  Allocate f5 on address: 0xc

## 第 48 页

输出结果是什么？

## 第 49 页

如果设置了pragma pack(1)，  结果又是什么？

## 第 50 页

如果设置了pragma pack(2)，  结果又是什么？

## 第 51 页

越界访问和缓冲区溢出攻击

## 第 52 页

越界访问和缓冲区溢出

数组存储区可看成是一个缓冲区，超越数组存储区范围的写入操作 称为缓冲区溢出。– 例如，对于一个有10个元素的char型数组，其定义的缓冲区有10个字 节。若写一个字符串到这个缓冲区，那么只要写入的字符串多于9个字 符（结束符‘\0’占一个字节），就会发生“写溢出”。– C语言程序中对数组的访问可能会有意或无意地超越数组存储区范围 而无法发现。缓冲区溢出是一种非常普遍、非常危险的漏洞，在各种操作系统、 应用软件中广泛存在。缓冲区溢出攻击是利用缓冲区溢出漏洞所进行的攻击。利用缓冲区 溢出攻击，可导致程序运行失败、系统关机、重新启动等后果。

## 第 53 页

共24字节

越界访问和缓冲区溢出

#include "stdio.h"

#include "string.h"

void outputs(char *str){char buffer[16];  strcpy(buffer,str);  printf("%s \n", buffer);}void hacker(void){printf("being hacked\n");}int main(int argc, char *argv[]){outputs(argv[1]);  return 0;

造成缓冲区溢出的原因是没有对栈中作为缓冲区的数组的访问 进行越界检查。举例：利用缓冲区溢出转到自设的程序hacker去执行outputs漏洞：当命令行中字符串超25个字符时，使用

strcpy函数就会使缓冲buffer造成写溢出并破坏返址

假定可执行文件名为test

16+4+4+1=25

Buffer的首地址

## 第 54 页

共24字节

越界访问和缓冲区溢出

test被反汇编得到的outputs汇编代码

080483e4 push	%ebp080483e5 mov	%esp,%ebp

080483e7 sub	$0x18,%esp

080483ea mov

080483ed mov

0x8(%ebp),%eax%eax,0x4(%esp)

080483f1 lea

080483f4 mov

0xfffffff0(%ebp),%eax%eax,(%esp)

080483f7 call  080483fc lea  080483ff mov

0x8048330 <strcpy>  0xfffffff0(%ebp),%eax%eax,0x4(%esp)

08048403 movl  0804840a call

$0x8048500,(%esp)  0x8048310

0804840f	leave  08048410 ret若strcpy复制了25个字符到buffer中，并将hacker首址置于结束符‘\0’  前4个字节，则在执行strcpy后，hacker代码首址被置于main栈帧返回地 址处，当执行outputs代码的ret指令时，便会转到hacker函数实施攻击。

## 第 55 页

程序的加载和运行

UNIX/Linux系统中，可通过调用execve()函数来加载并执行程序。execve()函数的用法如下：int execve(char *filename, char *argv[], *envp[]);filename是加载并运行的可执行文件名(如./hello)，可带参数列表 argv和环境变量列表envp。若错误（如找不到指定文件filename），则返回-1，并将控制权交给调用程序； 若函数执行成功，则不返回，最终将控制权传递到可执行目标中的主函数main。主函数main()的原型形式如下：int main(int argc, char **argv, char **envp);	或者：  int main(int argc, char *argv[], char *envp[]);argc指定参数列表长度，参数列表中开始是命令名（可执行文件名），最后以NULL结尾例如：参数列表（命令行）为“.\hello” 时，argc=2前述例子：“.\test 0123456789ABCDEFXXXX▥ ▧▥▧” ,argc=3argv[0]	argv[1]

字符串/指令

## 第 56 页

缓冲区溢出攻击

#include "stdio.h"  char code[]="0123456789ABCDEFXXXX""\x11\x84\x04\x08"  "\x00";int main(void){char *argv[3];  argv[0]="./test";  argv[1]=code;  argv[2]=NULL;  execve(argv[0],argv,NULL);  return 0;}

#include "stdio.h"

#include "string.h"void outputs(char *str)

char buffer[16];  strcpy(buffer,str);  printf("%s \n", buffer);

void hacker(void){printf("being hacked\n");}int main(int argc, char *argv[]){outputs(argv[1]);  return 0;

argv

argv[0]

null

argv[]

“./test＂

“0123456789ABCDEFXXXX▥ ▧▥▧”

argv[1]

可执行文件名为test

输入命令行：.\test 0123456789ABCDEFXXXX▥ ▧▥▧

按空格隔开的字符串 被构建成一个指针数组

## 第 57 页

越界访问和缓冲区

溢出

共24字节

假定hacker首址为0x08048411  void hacker(void) {printf("being hacked\n");}#include "stdio.h"  char code[]="0123456789ABCDEFXXXX""\x11\x84\x04\x08"  "\x00";int main(void) {  char *argv[3];  argv[0]="./test";  argv[1]=code;  argv[2]=NULL;execve(argv[0],argv,NULL);  return 0;}执行上述攻击程序后的输出结果为：  "0123456789ABCDEFXXXX▥ ▧▥▧being hacked  Segmentation fault

最后显示“Segmentation fault”，原因是 执行到hacker过程的ret指令时取到的“返回 地址”是一个不确定的值，因而可能跳转到数 据区或系统区或其他非法访问的存储区执行， 因而造成段错误。

## 第 58 页

x86-64指令系统概述

## 第 59 页

回顾：Intel处理器

已停产

现有产品

## 第 60 页

x86-64架构

背景Intel最早推出的64位架构是基于超长指令字VLIW技术的 IA-64体系结构，Intel 称其为显式并行指令计算机EPIC （  Explicitly Parallel Instruction Computer）。安腾和安腾2分别在2000年和2002年问世，它们是IA-64体 系结构的最早的具体实现，因为是一种全新的、与IA-32不 兼容的架构，所以，没有获得预期的市场份额。AMD公司利用Intel在IA-64架构上的失败，抢先在2003年 推出兼容IA-32的64位版本指令集x86-64，AMD获得了以 前属于Intel的一些高端市场。AMD后来将x86-64更名为 AMD64。Intel在2004年推出IA32-EM64T，它支持x86-64指令集。  Intel为了表示EM64T的64位模式特点，又使其与IA-64有 所区别，2006年开始把EM64T改名为Intel64。

## 第 61 页

回顾：IA-32支持的数据类型及格式

IA-32架构由16位架构发展而来，因此，虽然字长为32位或更大，但一个字为16位，长度后缀为 w；32位为双字，长度后缀为 l  long double实际长度为80位，但分配96位=12B（按4B对齐）

## 第 62 页

x86-64中各类数据的长度

## 第 63 页

x86-64的通用寄存器

新增8个64位通用寄存器（整数寄存器）R8、R9、R10、R11、R12、R13、R14和R15。可作为8位（R8B~R15B）、16位（R8W~R15W）或 32位寄存器（R8D~R15D）使用所有GPRs都从32位扩充到64位8个32位通用寄存器EAX、EBX、ECX、EDX、EBP、 ESP、ESI和 EDI对应扩展寄存器分别为RAX、RBX、 RCX、RDX、RBP、RSP、RSI和RDIEBP、ESP、ESI和 EDI的低8位寄存器分别是BPL、SPL、SIL和DIL可兼容使用原AH、BH、CH和DH寄存器（使原来IA-32中的每个通用寄存器都可以是8位、16位、  32位和64位，如：SIL、SI、ESI、RSI）

## 第 64 页

x86-64中寄存器的使用

–	指令可直接访问16个64位寄存器：RAX、RBX、RCX、RDX、 RBP、RSP、RSI、RDI，以及R8~R15指令可直接访问16个32位寄存器：EAX、EBX、ECX、EDX、EBP、ESP、ESI、EDI，以及R8D~R15D指令可直接访问16个16位寄存器：AX、BX、CX、DX、BP、SP、SI、DI，以及R8W~R15W指令可直接访问16个8位寄存器：AL、BL、CL、DL、BPL、SPL、SIL、DIL，以及R8B~R15B为向后兼容，指令也可直接访问AH、BH、CH、DH通过寄存器传送参数，因而很多过程不用访问栈，因此，与IA-32  不同，x86-64不需要帧指针寄存器，即RBP可用作普通寄存器使用程序计数器为64位寄存器RIP

## 第 65 页

回顾：IA-32的寄存器组织

返回值

调 用 者 保 存 ：  EAX、ECX、EDX被调用者保存：  EBX、ESI、EDI栈帧低部：EBP 栈帧顶部：ESP

## 第 66 页

x86-64通

用寄存器

通用寄存器 个数从8个增 加到16个，  宽度从32位 增加到64位增加了 %sil、%dil、%bpl、%spl 四个8位 寄存器%riw为16位%rib为8位（i=8~15）

## 第 67 页

x86-64的浮点寄存器

long double型数据虽然还采用80位（10B）扩展精度 格式，但所分配存储空间从12B扩展为16B，即改为 16B对齐方式，但不管是分配12B还是16B，都只用到 低10B128位的XMM寄存器从原来的8个增加到16个浮点操作指令集采用基于SSE的面向XMM寄存器的指令集，而不采用基于浮点寄存器栈的 x87 FPU 指令集浮点操作数存放在XMM寄存器中

## 第 68 页

回顾：IA-32的寄存器组织

x86-64继承了IA-32中的8、16、32位通用寄存器和128位XMM寄存器 而取消了IA-32中的80位浮点寄存器栈ST(0)-ST(7)

## 第 69 页

x86-64的寄存器

0123456789101112131415

%riw为16位%rib为8位（i=8~15）

16个128位寄 存器%xmmi（i=0~15）

增加了 %sil、%dil、%bpl、%spl 四个8位 寄存器

## 第 70 页

x86-64的基本指令

## 第 71 页

传送指令

数据传送指令（助记符“q”表示操作数长度为四字（即64位））  movabsq I, R：将64位立即数送64位通用寄存器(绝对的四字)movq：传送一个64位的四字（32位补码扩展为64位的四字）movsbq、movswq、movslq：将源操作数进行符号扩展并传送 到一个64位寄存器或存储单元中movzbq、movzwq：将源操作数进行零扩展后传送到一个64位寄 存器或存储单元中movl：功能相当于movzlq指令pushq S：R[rsp]←R[rsp]-8; M[R[rsp]] ←S  popq D： D← M[R[rsp]]; R[rsp]←R[rsp]-8

## 第 72 页

传送指令

数据传送指令举例以下函数功能是将类型为source_type 的参数转换为dest_type型数据并返回dest_type convert(source_type x) {  dest_type y = (dest_type) x;  return y;}

根据参数传递约定知，x在RDI对应 的适合宽度的寄存器（RDI、EDI、 DI和DIL）中，y存放在RAX对应的 寄存器（RAX、EAX、AX或AL）中，填写下表中的汇编指令以实现  convert函数中的赋值语句

问题：每种情况对应的 汇编指令各是什么？

## 第 73 页

传送指令

数据传送指令举例以下函数功能是将类型为source_type  的参数转换为dest_type型数据并返回dest_type convert(source_type x) {  dest_type y = (dest_type) x;  return y;}

根据参数传递约定知，x在RDI对应 的适合宽度的寄存器（RDI、EDI、 DI和DIL）中，y存放在RAX对应的 寄存器（RAX、EAX、AX或AL）中，填写下表中的汇编指令以实现  convert函数中的赋值语句

只需x的低32位

## 第 74 页

算术逻辑指令

常规的算术逻辑运算指令只要将原来IA-32中的指令扩展到64位即可。例如：addq（四字相加）subq（四字相减）incq（四字加1）decq（四字减1）imulq（带符号整数四字相乘）orq（64位相或）salq（64位算术左移）leaq（有效地址加载到64位寄存器）

## 第 75 页

算术逻辑指令

以下是C赋值语句“x=a*b+c*d;”对应的x86-64汇编代码已知x、a、b、c和d分别在寄存器RAX(x)、RDI(a)、RSI(b)、 RDX(c)和RCX(d)对应宽度的寄存器中根据以下汇编代码，推测x、a、b、c和d的数据类型

movslq %ecx, %rcx  imulq	%rdx, %rcx  movsbl %sil, %esi  imull %edi, %esi  movslq %esi, %rsi

leaq (%rcx, %rsi), %rax

d从32位符号扩展为64位，故d为int型 在RDX中的c为64位long型在SIL中的b为char型 在EDI中的a是int型

在RAX中的x是long型

## 第 76 页

算术逻辑指令

特殊的算术逻辑运算指令对于x86-64，还有一些特殊的算术逻辑运算指令。例如：  imulq S：R[rdx]:R[rax]← S * R[rax] (64位*64位带符号整数）  mulq S：R[rdx]:R[rax]← S * R[rax] (64位*64位无符号整数）cltq：R[rax] ← SignExtend(R[eax]) (将EAX内容符号扩展为四字）  clto： R[rdx]:R[rax]← SignExtend(R[rax]) (符号扩展为八字）  idivq S：R[rdx] ← R[rdx]:R[rax] mod S (带符号整数相除、余数）R[rax] ← R[rdx]:R[rax]÷S (带符号整数相除、商）  divq S：R[rdx] ← R[rdx]:R[rax] mod S (无符号整数相除、余数）R[rax] ← R[rdx]:R[rax]÷S (无符号整数相除、商）上述功能描述中，R[rdx]:R[rax]是一个128位的八字（oct word）

## 第 77 页

## 第 78 页

## 第 79 页

x86-64的过程调用

## 第 80 页

先看一个例子

对于以下C语言源文件sample.c：

在x86-64/Linux平台上用以 下命令执行汇编操作，得到与  IA-32兼容的汇编指令代码

$ gcc –O1 –S –m32 sample.c

%ebp%esp,	%ebp  8(%ebp),	%edx  12(%ebp), %eax  (%edx), %eax%eax, (%edx)%ebp

sample：  pushl  movl  movl  movl  addl  movl  popl  ret

long int sample(long int *xp, long int y){long int t=*xp+y;*xp=t;  return t;}在x86-64/Linux平台上用以 下命令执行汇编操作，得到 x86-64汇编指令代码

$ gcc –O1 –S –m64 sample.c

%rsi, %rax  (%rdi), %rax%rax, (%rdi)

sample：  movq  addq  movq  ret

在x86-64/Linux 平台上默认生成 x86-64格式代码，故可省略-m64

Long型数据长度不同 参数传递方式不同

## 第 81 页

x86-64过程调用的参数传递

通过通用寄存器传送参数，很多过程不用访问栈，故执行时间 比IA-32代码更短最多可有6个整型或指针型参数通过寄存器传递超过6个入口参数时，后面的通过栈来传递–	在栈中传递的参数若是基本类型，则都被分配8个字节call（或callq）将64位返址保存在栈中之前，执行R[rsp]←R[rsp]-8ret从栈中取出64位返回地址后，执行R[rsp]←R[rsp]+8

## 第 82 页

x86-64过程调用的寄存器使用约定

在过程(函数)  中尽量使用寄 存器RAX、 R10和R11。若使用RBX、  RBP、R12、 R13、R14和R15，则需要 将它们先保存 在栈中再使用，最后返回前 再恢复其值

## 第 83 页

x86-64过程调用举例

long caller ( ){char a=1；  short b=2；  int c=3；  long d=4；test(a, &a, b, &b, c, &c, d, &d);  return	a*b+c*d;

void test(char a, char *ap,

short b, short *bp,  int c, int *cp,long d, long *dp)

{*ap+=a;*bp+=b;*cp+=c;*dp+=d;}

其他6个参数在哪里？

执行到caller的call指令 前，栈中的状态如何？

## 第 84 页

举例：caller函数中部分指令

long caller ( ){char a=1；  short b=2；  int c=3；  long d=4；test(a, &a, b, &b, c, &c, d, &d);  return	a*b+c*d;}

第15条指令

## 第 85 页

举例：test函数中部分指令

执行到test的ret指令前，栈中的 状态如何？ret执行后怎样？

DIL、RSI、DX、RCX、R8D、R9void test(char a, char *ap,short b, short *bp,  int c, int *cp,long d, long *dp){*ap+=a;*bp+=b;*cp+=c;*dp+=d;}

16

R[r10]←&d*ap+=a;*bp+=b;*cp+=c;*dp+=d;

## 第 86 页

举例：caller函数中部分指令

long caller ( ){char a=1；  short b=2；  int c=3；  long d=4；test(a, &a, b, &b, c, &c, d, &d);  return	a*b+c*d;}

执行test的ret指令后，栈中的状 态如何？

释放caller的栈帧

执行到ret指令时，  RSP指向调用caller  函数时保存的返回值

从第16条指令开始

## 第 87 页

IA-32和x86-64的比较

例：以下是一段C语言代码：

#include <stdio.h>  main(){double a = 10;  printf("a = %d\n", a);}

在IA-32上运行时，打印结果为a=0在x86-64上运行时，打印一个不确定值 为什么？

在IA-32中a为float型又怎样呢？先执行flds，再执行fstpl即：flds将32位单精度转换为80位格式入浮点寄存器栈，fstpl再将  80位转换为64位送存储器栈中，故实际上与a是double效果一样！

10=1010B=1.01×23阶码e=1023+3=10000000010B10的double型表示为：0 10000000010 0100…0B即4024 0000 0000 0000H先执行fldl，再执行fstpl

fldl：局部变量区→ST(0)  fstpl：ST(0) →参数区

## 第 88 页

IA-32过程调用参数传递

a的机器数对应十六进制为：40 24 00 00 00 00 00 00H

参数2参数1

打印结果总是全0

## 第 89 页

回顾：x86-64的浮点寄存器

long double型数据虽然还采用80位（10B）扩展精度 格式，但所分配存储空间从12B扩展为16B，即改为 16B对齐方式，但不管是分配12B还是16B，都只用到 低10B128位的XMM寄存器从原来的8个增加到16个浮点操作指令集采用基于SSE的面向XMM寄存器的指 令集，而不采用基于浮点寄存器栈的 x87 FPU 指令集浮点操作数存放在XMM寄存器中

## 第 90 页

x86-64过程调用参数传递

printf中为%d，故将从ESI中 取打印参数进行处理；但a是 double型数据，在x86-64  中，a的值被送到XMM寄存 器中而不会送到 ESI 中。故 在printf执行时，从ESI 中读 取的并不是a的低32位，而是 一个不确定的值。

main(){double a = 10;  printf("a = %d\n", a);}.LC1:.string "a = %d\n“……movsd	.LC0(%rip), %xmm0 //a 送xmm0

.LC0:

.long.long

01076101120

movl	$.LC1, %edi //RDI 高32位为0  movl	$1, %eax	//向量寄存器个数 call		printfaddq	$8, %rspret	因为printf第2个参数为double型，……	故向量寄存器个数为1

00000000H40240000H

小端方式！0存在低地址上

