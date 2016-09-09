Object Stack Allocation
=======================
[Last updated: September 9, 2016]

Objective
---------
**Definition:** The object `p` *escapes* the method `M` if the lifetime of `p` can be longer than `M`. In other words,
if there is any way to access the object `p` outside of the method `M` (using static or non-static fields, method
arguments or return value, exception catch block, finalization queue or by object's address exposure) then the object
`p` escapes the method `M`. If an object doesn't escape the method JIT compiler can replace the call to a JIT helper
allocating the object on the heap by the instructions allocating the local variable on the stack. We can extend the 
definition of *escaped object* to the definition of *escaped local reference variable* meaning that the lifetime of 
such variable can be longer that the lifetime of the method.

The main objective is to allocate objects on the stack rather on the GC heap when it is legal and profitable. This
should move memory pressure off of the GC.

Mechanics
---------
Previously RyuJIT's importer while reading MSIL bytecode and creating IR of the loading method also lowered `NewObj`
instructions into two consecutive statements:

1. Call to the helper function allocating object on the heap (e.g. `HELPER.CORINFO_HELP_NEWSFAST`)
2. Call to the constructor

We introduce a designated node type `GT_ALLOCOBJ` and defer creation of a call to the helper function. We also introduce 
a designated phase `ObjectAllocator` in the JIT that does escape analysis, loop detection in CFG and lowers
`GT_ALLOCOBJ` node to either the helper function allocating object on the heap or instructions allocating object on the 
stack depending on the results of these analyses and some other conditions preventing object stack allocation.

We can enable object stack allocation using `COMPlus_JitObjectStackAllocation` flag (which is 0 by default).

Escape analysis
---------------
There are different methods to approach and solve escape analysis problem [[1]](#[1]), [[2]](#[2]), [[3]](#[3]), 
[[4]](#[4]).
Our implementation is inspired mainly by [[1]](#[1]). We have started with quite conservative version of the algorithm.
The idea of this escape analysis approach is built around a framework called the *connection graph*. The connection
graph abstracts the "connectivity" between objects, static or non-static fields and local variables of reference type. 
We build a connection graph by walking over all expression nodes in IR. We also determine the set of local variables that 
escape the method while building the graph. Then, we do reachability analysis on this graph from the set of escaping
variables. This partitions the connection graph into two parts: first part contains objects and variables that escape
the method, second part contains only the ones that don't escape. Using this information RyuJIT lowers `GT_ALLOCOBJ` 
nodes to either the helper function allocating object on the heap or instructions allocating object on the stack.

Lowering GT_ALLOCOBJ nodes
--------------------------
RyuJIT determines if `NewObj` instruction(s) were originally present in the current method and a basic block by checking
flags `OMF_HAS_NEWOBJ` and `BBF_HAS_NEWOBJ`. Then, in each basic block where `BBF_HAS_NEWOBJ` flag is set RyuJIT looks 
for `GT_ALLOCOBJ` nodes in so-called *canonical* form:

```
▌  stmtExpr  void
│  ┌──▌  allocObj  ref   
│  │  └──▌  const(h)  long   0xd1ffab1e method
└──▌  =         ref   
   └──▌  lclVar    ref    V01 tmp0         
```

and lowers them.

Lowering a `GT_ALLOCOBJ` node to the helper function allocating object on the heap transforms the tree containing 
`GT_ALLOCOBJ` node into the following tree:

```
┌──▌  call help ref    HELPER.CORINFO_HELP_NEWSFAST
│  └──▌  const(h)  long   0xd1ffab1e method
▌  =         ref   
└──▌  lclVar    ref    V01 tmp0     
```

Lowering a `GT_ALLOCOBJ` node to instructions allocating object on the stack allocates a long lifetime temp and 
generates the following trees:

```	
▌  stmtExpr  void
│  ┌──▌  const     int    32
└──▌  initBlk   void  
│  ┌──▌  const     int    0
└──▌  <list>    void  
   └──▌  addr      byref 
      └──▌  lclVar    struct V02 tmp1

      
▌  stmtExpr  void
│  ┌──▌  const(h)  long   0xd1ffab1e method
└──▌  =         long  
   └──▌  lclFld    long   V02 tmp1         [+8]


▌  stmtExpr  void
│     ┌──▌  const     int    8
│  ┌──▌  +         long  
│  │  └──▌  addr      byref 
│  │     └──▌  lclVar    struct V02 tmp1
└──▌  =         ref   
   └──▌  lclVar    ref    V01 tmp0      
```

Here, first statement zeroes memory allocated on the stack, second statement initializes `pEEType` fields of the 
stack-allocated object, third statement copy address to the beginning of the object to a short lifetime temp `tmp0`.

Loop detection
--------------
RyuJIT has an ability to identify natural loops in order to do their optimization. However, we need to find all cycles
in CFG and allow only heap allocation of objects that are not inside any cycle. We can allocate an object on the stack 
only if the object doesn't escape the iteration of the loop in which it is allocated. However, such analysis is 
complicated for an arbitrary loop.

To determine all cycles in CFG we implement classical Tarjan's algorithm [[5]](#[5]) for identifying strongly 
connected components.


Other conditions preventing object stack allocation
---------------------------------------------------
The following list describes the conditions when the object must be allocated on the heap:

* A class defines the finalizer method. This implies that all instances of such class can escapes the method via the 
finalizer queue.
* An object size exceeds some predefined limit.

The following demonstrates possible scenarios when an object can (or can not ) be allocated on the stack in current
implementation.

Scenario 1
----------
An object pointed by `lclVar1` and `lclVar2` escapes if any of these variables escapes. We have to assume that the 
object escapes if the constructor call `Foo:ctor` is not inlined since we don't have escape information for any callees.

```
Foo lclVar1 = new Foo();

lclVar1.Field1 = 1;
lclVar1.Field2 = 2;
lclVar1.Field3 = lclVar1.Field1 + lclVar1.Field2;

Foo lclVar2 = lclVar1;
```

Scenario 2
----------
To be able to stack allocate an object pointed by `lclVar` both constructor call and method call must be inlined since 
we don’t have interprocedural escape information.

```
Foo lclVar = new Foo();

lclVar.Field1 = 1;
lclVar.Field2 = 2;
lclVar.Field3 = lclVar.Field1 + lclVar.Field2;

lclVar.NonVirtualMethod();
```

Scenario 3
----------
An object pointed by `lclVar` can escape via parameter of method `Bar`, so we can only attempt to stack allocate 
`Foo` object if the call to `Bar` has been inlined.

```
Foo lclVar = new Foo();

lclVar.Field1 = 1;
lclVar.Field2 = 2;
lclVar.Field3 = lclVar.Field1 + lclVar.Field2;

Bar(lclVar);
```

Scenario 4
----------
The constraints here should be *`lclVar1` escapes if `lclVar2` escapes*. However, current implementation is not 
considering fields of an object in escape analysis and marks all variables assigned to an expression which is 
non-local variable (e.g., `lclVar1`) as escaping a method.

```
Foo lclVar1 = new Foo();

lclVar1.Field1 = 1;
lclVar1.Field2 = 2;
lclVar1.Field3 = lclVar1.Field1 + lclVar1.Field2;

Bar lclVar2 = new Bar();

lclVar2.Field1 = lclVar1;
```

Scenario 5
----------
The best scenario here is to allocate `lclVar` on the stack since the pointed object does not escape an iteration of 
for-loop. However, this analysis is complicated for an arbitrary loop and we do mark such variables as escaping a 
method.

```
for (int i = 0; i < 10; ++i) 
{
  Foo lclVar = new Foo();

  lclVar.Field1 = 1;
  lclVar.Field2 = 2;
  lclVar.Field3 = lclVar.Field1 + lclVar.Field2;
}
```

Scenario 6
----------
`lclVar` escapes a method since it is returned from the method.

```
static Foo Bar()
{
  Foo lclVar = new Foo();

  lclVar.Field1 = 1;
  lclVar.Field2 = 2;
  lclVar.Field3 = lclVar.Field1 + lclVar.Field2;

  return lclVar;
}
```

Current limitations
-------------------
* To simplify an escape analysis implementation, RyuJIT views any object as single and monolithic. A possible 
improvement can be representating an object as a tree where the root of the tree is object itself and the children of
the root are object’s reference fields.
* Since we don't have interprocedural information our algorithm relies on inlining results.

Current results
---------------
Taking into account that implemented escape analysis is extremely conservative we have very modest results as a starting
point:

* 21 objects while crossgen-ing `System.Private.CoreLib` have been allocated on the stack. Most of them are ephemeral objects created 
in the class `System.Internal` in the method `CommonlyUsedGenericInstantiations`.
* 26 objects while ngen-ing mscorlib have been allocated on the stack. This includes an enumerator and a wrapper object for collection.

Opportunities Analysis
----------------------
Suppose that no GT_CALL nodes cause object escapement. Such assumption can give us an upper bound of objects 
that can be allocated on the stack if we have interprocedural information. The following numbers reflect such analysis
while crossgen-ing System.Private.CoreLib in CoreCLR:

* The number of methods where at least one `GT_ALLOCOBJ` is found and allocated on the stack: 424 (out of 6150 methods in 
total)
* The number of `GT_ALLOCOBJ` nodes transformed to stack allocation:  586 (out of 7977 nodes in total)

Suprisingly, we found that the most part of objects allocated by `NewObj` instruction in `System.Private.CoreLib` are 
exceptions (5345 objects). There is no point of considering them as possible candidates for stack allocation. Taking 
into account this we have that 586 of 2632 objects (22.2%) can be allocated on the stack in the best case scenario. 

We also collected these numbers for mscorlib in Desktop CLR:

* The number of methods where at least one `GT_ALLOCOBJ` found and allocated on the stack: 1218 (out of 8758 methods in
total)
* The number of `GT_ALLOCOBJ` nodes transformed to stack allocation:  1774 (out of 15471 nodes in total)
* The number of exception objects: 9200

Hence we have 1774 of 6271 objects (28.3%) that can be allocated on the stack in the best case scenario.

Workarounds
-----------
* If at least one object in the method is stack allocated we currently restrict RyuJIT compiler to use only checked 
write barriers inside this method.
* There is a function `Object::ValidateInner` where VM checks there is a GC_REF pointer points either on the large 
objects heap or the small objects heap:
```
CHECK_AND_TEAR_DOWN(bSmallObjectHeapPtr || bLargeObjectHeapPtr)
```
This method can be called from different places. For example, when GC reports live objects in 
`GcInfoDecoder::ReportRegisterToGC` it calls `VALIDATE_ROOT` which calls `Object::ValidateInner`. We mitigated this by
making JIT reporting all objects as GC_BYREF in case if at least one object has been stack allocated. We can determine
if a method has a stack allocated object by checking flag `OMF_HAS_OBJSTACKALLOC`.
* We currently initialize memory allocated on the stack with zeroes. However, in `DEBUG` `ObjHeader` contains 
information about AppDomainIndex set in `Object::SetAppDomain`. Since ObjHeader is not always zero we should consider to
do its proper initialization. We probably need to add one more method in EE interface to do so.
* We have to add `gtCost`/`gtSize` estimates for `GT_ALLOCOBJ` node in `gtSetEvalOrder`.
* Since SuperPMI became an open-source project we need to properly implement all methods added to EE interface (listed
below).

Future Improvements
-------------------
1. We tried to see if our object stack allocation mechanism can be applied to allocate on the stack boxed object. The 
problem here is that we don't have a handle for the boxed object and reusing the struct handle makes it ambiguous as to 
what's allocated on the stack: the actual struct or the boxed struct.
1. Our current escape analysis implementation views an object as a single, monolithic thing. The original idea described
in paper by [[1]](#[1]) is to represent an object with its fields as a tree, where the object itself is the root of the
tree and object's fields are children of the root. This should handle the situations where a reference variable assigned
to another object's field: `p.f = q` and where an object's field assigned to a reference variable: `p = q.f`.
1. We should add special handling of comma, helper calls and other specific nodes in escape analysis.
1. We should reuse/extend this mechanism for array stack allocation. This is likely be useful for `params`-arguments
when a caller packs `vararg`-reference arguments into array and a callee immediatly unpacks this array.
1. We should add in our escape analysis ability to analyze if a reference variable can point to either the heap or the 
stack or to both. Then, we can decide on if for this variable we should use CheckedWriteBarrier or WriteBarrier or not 
use WriteBarrier at all. Such an analysis will also allow us not to report all GC variables as `GC_BYREF`.
1. We should use dynamic stack allocations for objects whose allocations are not executed on all paths through the 
program.

Changes made in JIT functions
-----------------------------
* `lvaSetStruct` was extended to be able to allocate an object on the stack

Methods added to EE interface
-----------------------------
* `getObjHeaderSize` returns `sizeof(ObjHeader)`
* `getHeapClassSize(clsHnd)` returns the size of an object
* `classHasFinalizer(clsHnd)` returns true if a class defines finalizer

Location of GitHub fork
-----------------------
This functionality can be found at GitHub fork 
[echesakov/coreclr](https://github.com/echesakov/coreclr/tree/StackAllocation).

References
----------
<a name="[1]"/>
[1] Choi, Jong-Deok, et al. "Escape analysis for Java." Acm Sigplan Notices 34.10 (1999): 1-19.

<a name="[2]"/>
[2] Kotzmann, Thomas, and Hanspeter Mössenböck. "Escape analysis in the context of dynamic compilation and 
deoptimization." Proceedings of the 1st ACM/USENIX international conference on Virtual execution environments. ACM, 
2005.

<a name="[3]"/>
[3] Gay, David, and Bjarne Steensgaard. "Fast escape analysis and stack allocation for object-based programs." 
International Conference on Compiler Construction. Springer Berlin Heidelberg, 2000.

<a name="[4]"/>
[4] Stadler, Lukas, Thomas Würthinger, and Hanspeter Mössenböck. "Partial escape analysis and scalar replacement for 
Java." Proceedings of Annual IEEE/ACM International Symposium on Code Generation and Optimization. ACM, 2014. 

<a name="[5]"/>
[5] Tarjan, Robert. "Depth-first search and linear graph algorithms." SIAM journal on computing 1.2 (1972): 146-160.