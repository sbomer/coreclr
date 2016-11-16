// Licensed to the .NET Foundation under one or more agreements.
// The .NET Foundation licenses this file to you under the MIT license.
// See the LICENSE file in the project root for more information.

/*XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
XX                                                                           XX
XX                         ObjectAllocator                                   XX
XX                                                                           XX
XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
*/

#include "jitpch.h"
#ifdef _MSC_VER
#pragma hdrstop
#endif

//===============================================================================

//------------------------------------------------------------------------
// DoPhase: Run analysis (if object stack allocation is enabled) and then
//          morph each GT_ALLOCOBJ node either into an allocation helper
//          call or stack allocation.
// Notes:
//    Runs only if Compiler::optMethodFlags has flag OMF_HAS_NEWOBJ set.
void ObjectAllocator::DoPhase()
{
    if ((comp->optMethodFlags & OMF_HAS_NEWOBJ) == 0)
    {
        return;
    }

    if (IsObjectStackAllocationEnabled())
    {
        DoAnalysis();
    }

    MorphAllocObjNodes();
}

struct ObjectAllocator::BuildConnGraphVisitorCallbackData
{
    BuildConnGraphVisitorCallbackData(ObjectAllocator* caller, BitVec* connGraphPointees) :
        m_caller(caller), m_connGraphPointees(connGraphPointees)
    {
    }

    void MarkLclVarAsNonStackAlloc(unsigned int lclNum)
    {
        BitVecOps::AddElemD(&m_caller->m_bitVecTraits, m_caller->m_EscapingPointers, lclNum);
    }

    void SetPointerPointeeRel(unsigned int pointerLclNum, unsigned int pointeeLclNum)
    {
        BitVecOps::AddElemD(&m_caller->m_bitVecTraits, m_connGraphPointees[pointerLclNum], pointeeLclNum);
    }

private:
    ObjectAllocator* m_caller;
    BitVec*          m_connGraphPointees;
};

//------------------------------------------------------------------------
// DoAnalysis: Walk over basic blocks of the method and detect all local
//             variables that can be allocated on the stack.
//
// Assumptions:
//    Must be run after the dominators have been computed (we need this
//    information to detect loops).
void ObjectAllocator::DoAnalysis()
{
    assert(m_IsObjectStackAllocationEnabled);
    assert(comp->fgDomsComputed);
    assert(!m_AnalysisDone);

    if (comp->lvaCount > 0)
    {
        m_EscapingPointers = BitVecOps::MakeEmpty(&m_bitVecTraits);

        BitVec* connGraphPointees;
        BitVec* connGraphPointers;

        BuildConnGraph(&connGraphPointees);
        ComputeReachableNodes(&m_bitVecTraits, connGraphPointees, m_EscapingPointers);
    }

    m_AnalysisDone = true;
}

void ObjectAllocator::BuildConnGraph(BitVec** pConnGraphPointees)
{
    assert(pConnGraphPointees);

    *pConnGraphPointees       = new (comp->getAllocator()) BitSetShortLongRep[comp->lvaCount];
    BitVec* connGraphPointees = *pConnGraphPointees;

    BuildConnGraphVisitorCallbackData callbackData(this, connGraphPointees);

    for (unsigned int lclNum = 0; lclNum < comp->lvaCount; ++lclNum)
    {
        var_types type = comp->lvaTable[lclNum].TypeGet();

        if (type == TYP_REF || type == TYP_I_IMPL || type == TYP_BYREF)
        {
            // A local variable of TYP_REF can potentially points to other local variables
            // For such variable we maintain bit-set of pointees
            connGraphPointees[lclNum] = BitVecOps::MakeEmpty(&m_bitVecTraits);

            if (comp->lvaTable[lclNum].lvAddrExposed)
            {
                callbackData.MarkLclVarAsNonStackAlloc(lclNum);
            }
        }
        else
        {
            // Other local variable will not participate in our analysis
            connGraphPointees[lclNum] = BitVecOps::UninitVal();
        }
    }

    BasicBlock* block;

    foreach_block(comp, block)
    {
        for (GenTreeStmt* stmt = block->firstStmt();
            stmt;
            stmt = stmt->gtNextStmt)
        {
            const bool lclVarsOnly  = false;
            const bool computeStack = true;

            comp->fgWalkTreePre(&stmt->gtStmtExpr, BuildConnGraphVisitor, &callbackData, lclVarsOnly, computeStack);
        }
    }
}

void ObjectAllocator::ComputeReachableNodes(BitVecTraits* bitVecTraits, BitVec* adjacentNodes, BitVec& reachableNodes)
{
    BitSetShortLongRep pointers = BitVecOps::MakeCopy(bitVecTraits, reachableNodes);
    BitSetShortLongRep pointees = BitVecOps::UninitVal();

    unsigned int lclNum;

    bool doOneMoreIteration = true;
    while (doOneMoreIteration)
    {
        BitVecOps::Iter iterator(bitVecTraits, pointers);
        doOneMoreIteration = false;

        while (iterator.NextElem(bitVecTraits, &lclNum))
        {
            doOneMoreIteration = true;

            // pointees         = adjacentNodes[lclNum]
            BitVecOps::Assign(bitVecTraits, pointees, adjacentNodes[lclNum]);
            // pointees         = pointees \ reachableLclVars
            BitVecOps::DiffD(bitVecTraits, pointees, reachableNodes);
            // pointers         = pointers U pointees
            BitVecOps::UnionD(bitVecTraits, pointers, pointees);
            // reachableLclVars = reachableLclVars U pointees
            BitVecOps::UnionD(bitVecTraits, reachableNodes, pointees);
            // pointers         = pointers \ { lclNum }
            BitVecOps::RemoveElemD(bitVecTraits, pointers, lclNum);
        }
    }
}

//------------------------------------------------------------------------
// MorphAllocObjNodes: Morph each GT_ALLOCOBJ node either into an
//                     allocation helper call or stack allocation.
//
// Notes:
//    Runs only over the blocks having bbFlags BBF_HAS_NEWOBJ set.
void ObjectAllocator::MorphAllocObjNodes()
{
    TarjanStronglyConnectedComponents tarjanScc(comp);
    
    if (IsObjectStackAllocationEnabled())
    {
        tarjanScc.DoAnalysis();
    }

    BasicBlock* block;

    foreach_block(comp, block)
    {
        const bool basicBlockHasNewObj = (block->bbFlags & BBF_HAS_NEWOBJ) == BBF_HAS_NEWOBJ;
#ifndef DEBUG
        if (!basicBlockHasNewObj)
        {
            continue;
        }
#endif // DEBUG

        for (GenTreeStmt* stmt = block->firstStmt(); stmt; stmt = stmt->gtNextStmt)
        {
            GenTreePtr stmtExpr = stmt->gtStmtExpr;
            GenTreePtr op2      = nullptr;

            bool canonicalAllocObjFound = false;

            if (stmtExpr->OperGet() == GT_ASG && stmtExpr->TypeGet() == TYP_REF)
            {
                op2 = stmtExpr->gtGetOp2();

                if (op2->OperGet() == GT_ALLOCOBJ)
                {
                    canonicalAllocObjFound = true;
                }
            }

            if (canonicalAllocObjFound)
            {
                assert(basicBlockHasNewObj);
                //------------------------------------------------------------------------
                // We expect the following expression tree at this point
                //  *  GT_STMT   void  (top level)
                // 	|  /--*  GT_ALLOCOBJ   ref
                // 	\--*  GT_ASG    ref
                // 	   \--*  GT_LCL_VAR    ref
                //------------------------------------------------------------------------

                GenTreePtr op1 = stmtExpr->gtGetOp1();

                assert(op1->OperGet() == GT_LCL_VAR);
                assert(op1->TypeGet() == TYP_REF);
                assert(op2 != nullptr);
                assert(op2->OperGet() == GT_ALLOCOBJ);

                GenTreeAllocObj* asAllocObj = op2->AsAllocObj();
                unsigned int     lclNum     = op1->AsLclVar()->GetLclNum();
                CORINFO_CLASS_HANDLE clsHnd = op2->AsAllocObj()->gtAllocObjClsHnd;

                if (IsObjectStackAllocationEnabled() && CanAllocateLclVarOnStack(lclNum, clsHnd)  && !tarjanScc.IsPartOfCycle(block->bbNum))
                {
#if DEBUG
                    if (comp->verbose)
                    {
                        printf("Allocating local variable %d on the stack in the class %s in the method %s\n", lclNum, comp->info.compClassName, comp->info.compMethodName);
                    }
#endif // DEBUG

                    op2 = MorphAllocObjNodeIntoStackAlloc(asAllocObj, block, stmt);
                    comp->optMethodFlags |= OMF_HAS_OBJSTACKALLOC;
                }
                else
                {
                    op2 = MorphAllocObjNodeIntoHelperCall(asAllocObj);
                }

                comp->fgMorphBlockStmt(block, stmt DEBUGARG("MorphAllocObjNodes"));

                // Propagate flags of op2 to its parent.
                stmtExpr->gtOp.gtOp2 = op2;
                stmtExpr->gtFlags |= op2->gtFlags & GTF_ALL_EFFECT;
            }

#ifdef DEBUG
            else
            {
                // We assume that GT_ALLOCOBJ nodes are always present in the
                // canonical form.
                comp->fgWalkTreePre(&stmt->gtStmtExpr, AssertWhenAllocObjFoundVisitor);
            }
#endif // DEBUG
        }
    }
}

//------------------------------------------------------------------------
// MorphAllocObjNodeIntoHelperCall: Morph a GT_ALLOCOBJ node into an
//                                  allocation helper call.
//
// Arguments:
//    allocObj - GT_ALLOCOBJ that will be replaced by helper call.
//
// Return Value:
//    Address of helper call node (can be the same as allocObj).
//
// Notes:
//    Must update parents flags after this.
GenTreePtr ObjectAllocator::MorphAllocObjNodeIntoHelperCall(GenTreeAllocObj* allocObj)
{
    assert(allocObj != nullptr);

    GenTreePtr op1 = allocObj->gtGetOp1();

    GenTreePtr helperCall = comp->fgMorphIntoHelperCall(allocObj, allocObj->gtNewHelper, comp->gtNewArgList(op1));

    return helperCall;
}

//------------------------------------------------------------------------
// MorphAllocObjNodeIntoStackAlloc: Morph a GT_ALLOCOBJ node into stack
//                                  allocation.
// Arguments:
//    allocObj - GT_ALLOCOBJ that will be replaced by helper call.
//    block    - a basic block where allocObj is
//    stmt     - a statement where allocObj is
//
// Return Value:
//    Address of tree doing stack allocation (can be the same as allocObj).
//
// Notes:
//    Must update parents flags after this.
//    This function can insert additional statements before stmt.
GenTreePtr ObjectAllocator::MorphAllocObjNodeIntoStackAlloc(GenTreeAllocObj* allocObj,
                                                            BasicBlock*      block,
                                                            GenTreeStmt*     stmt)
{
    assert(allocObj != nullptr);
    assert(m_AnalysisDone);

    unsigned int lclNum;

    lclNum = comp->lvaGrabTemp(false DEBUGARG("MorphAllocObjNodeIntoStackAlloc temp")); // Lifetime of this local variable can be longer than one BB
    comp->lvaSetStruct(lclNum, allocObj->gtAllocObjClsHnd, true);

    unsigned int structSize = comp->lvaTable[lclNum].lvSize();

    GenTreePtr tree;

    //------------------------------------------------------------------------
    // *  GT_STMT  void  (top level)
    // |  /--*  GT_CNS_INT
    // \--*  GT_INITBLK   void
    //    |  /--*  GT_CNS_INT     int    0
    //    \--*  <list>    void
    //       \--*  GT_ADDR      byref
    //          \--*  GT_LCL_VAR    struct(AX)
    //------------------------------------------------------------------------

    tree = comp->gtNewLclvNode(lclNum, TYP_STRUCT);
    tree = comp->gtNewOperNode(GT_ADDR, TYP_BYREF, tree);
    tree = comp->gtNewBlkOpNode(comp->gtNewLclvNode(lclNum, TYP_STRUCT), // Dest
                                comp->gtNewIconNode(0), // Value
                                structSize, // Size
                                true, // isVolatile
                                false); // not copyBlock

    tree = comp->gtNewStmt(tree);

    comp->fgInsertStmtBefore(block, stmt, tree);
    comp->fgMorphBlockStmt(block, tree DEBUGARG("MorphAllocObjNodeIntoStackAlloc"));

    //------------------------------------------------------------------------
    // *  GT_STMT   void
    // |  /--*  GT_CNS_INT  long
    // \--*  GT_ASG    long
    //    \--*  GT_IND     long
    //       \--*  GT_ADDR      byref               
    //          \--*  GT_LCL_VAR    struct(AX)
    //------------------------------------------------------------------------

    const unsigned objHeaderSize = comp->info.compCompHnd->getObjHeaderSize();

    tree = comp->gtNewLclvNode(lclNum, TYP_STRUCT);
    tree = comp->gtNewOperNode(GT_ADDR, TYP_BYREF, tree);
    tree = comp->gtNewOperNode(GT_ADD, TYP_BYREF, tree, comp->gtNewIconNode(objHeaderSize));

    GenTreePtr op1;

    op1  = allocObj->gtGetOp1();
    tree = comp->gtNewOperNode(GT_IND, op1->TypeGet(), tree);
    tree = comp->gtNewAssignNode(tree, op1);

    tree = comp->gtNewStmt(tree);

    comp->fgInsertStmtBefore(block, stmt, tree);
    comp->fgMorphBlockStmt(block, tree DEBUGARG("MorphAllocObjNodeIntoStackAlloc"));

    //------------------------------------------------------------------------
    // *  GT_STMT   void
    // |  / --*  GT_ADDR      long
    // |  |   \--*  GT_LCL_VAR    struct
    // \--*  GT_ASG    ref
    //    \--*  GT_LCL_VAR    ref
    //------------------------------------------------------------------------

   /* allocObj->ChangeOper(GT_ADDR);
    allocObj->gtType = TYP_I_IMPL;

    tree = comp->gtNewLclvNode(lclNum, TYP_STRUCT);
    allocObj->gtOp1 = tree;*/
    allocObj->ChangeOper(GT_ADD);
    allocObj->gtType = TYP_I_IMPL;

    tree = comp->gtNewLclvNode(lclNum, TYP_STRUCT);
    tree = comp->gtNewOperNode(GT_ADDR, TYP_BYREF, tree);
    allocObj->gtOp1 = tree;

    tree = comp->gtNewIconNode(objHeaderSize);
    allocObj->gtOp.gtOp2 = tree;

    return allocObj;
}

Compiler::fgWalkResult ObjectAllocator::BuildConnGraphVisitor(GenTreePtr* pTree, Compiler::fgWalkData* data)
{
    GenTreePtr tree = *pTree;
    assert(tree);

    if (tree->OperGet() == GT_LCL_VAR && (tree->TypeGet() == TYP_REF || tree->TypeGet() == TYP_I_IMPL))
    {
        Compiler* compiler                              = data->compiler;
        GenTreePtr parent                               = data->parent;
        BuildConnGraphVisitorCallbackData* callbackData = reinterpret_cast<BuildConnGraphVisitorCallbackData*>(data->pCallbackData);

        unsigned int lclNum = tree->AsLclVar()->GetLclNum();

        if (parent->OperGet() == GT_ASG)
        {
            GenTreePtr op1 = parent->AsOp()->gtGetOp1();

            // We don't do any analysis when lclVar on the lhs of GT_ASG node
            // If there is another local variable on the rhs, eventually, we
            // will be there. Otherwise, we can ignore this assignment.
            if (op1 != tree)
            {
                // lclVar is on the rhs of GT_ASG node
                assert(parent->AsOp()->gtGetOp2() == tree);

                if (op1->OperGet() == GT_LCL_VAR)
                {
                    //------------------------------------------------------------------------
                    // We expect the following tree at this point
                    //   /--*  GT_LCL_VAR    ref    pointeeLclVar
                    // --*  =         ref
                    //   \--*  GT_LCL_VAR    ref    pointerLclVar
                    //------------------------------------------------------------------------
                    const unsigned int pointerLclNum = op1->AsLclVar()->GetLclNum();
                    const unsigned int pointeeLclNum = lclNum;

                    callbackData->SetPointerPointeeRel(pointerLclNum, pointeeLclNum);
                }
                else
                {
                    //------------------------------------------------------------------------
                    // Use the following conservative behaviour for GT_ASG parent node:
                    //   Do not allow local variable (TYP_REF) to be allocated on the stack if
                    //   1. lclVar appears on the rhs of a GT_ASG node
                    //                      AND
                    //   2. The lhs of the GT_ASG is not another lclVar
                    //------------------------------------------------------------------------
                    callbackData->MarkLclVarAsNonStackAlloc(lclNum);
                }
            }
        }
        else if (parent->OperGet() == GT_ADD)
        {
            parent = data->parentStack->Index(2);

            if (parent->OperGet() == GT_ASG)
            {
                GenTreePtr op1 = parent->AsOp()->gtGetOp1();

                if (op1->OperGet() == GT_LCL_VAR)
                {
                    const unsigned int pointerLclNum = op1->AsLclVar()->GetLclNum();
                    const unsigned int pointeeLclNum = lclNum;

                    callbackData->SetPointerPointeeRel(pointerLclNum, pointeeLclNum);
                }
            }
            else if (CanLclVarEscapeViaParentStack(data->parentStack, data->compiler))
            {
                callbackData->MarkLclVarAsNonStackAlloc(lclNum);
            }
        }
        else if (CanLclVarEscapeViaParentStack(data->parentStack, data->compiler))
        {
            callbackData->MarkLclVarAsNonStackAlloc(lclNum);
        }
    }
    return Compiler::fgWalkResult::WALK_CONTINUE;
}

//------------------------------------------------------------------------
// CanLclVarEscapeViaParentStack: TODO
//
// Arguments:
//    parentStack - 
//    compiler    - 
bool ObjectAllocator::CanLclVarEscapeViaParentStack(ArrayStack<GenTreePtr>* parentStack, Compiler* compiler)
{
    assert(parentStack);

    //--------------------------------------------------------------------------
    // We consider only the following simplest scenarios for now:
    //   1. When node.parent is any of the following nodes: GT_IND, GT_EQ, GT_NE
    //   2. When node.parent is GT_ADD and node.parent.parent is GT_IND
    //   3. When node.parent is GT_CALL to a pure helper
    //--------------------------------------------------------------------------

    bool canLclVarEscapeViaParentStack = true;

    GenTreePtr ancestor;

    if (parentStack->Height() > 1)
    {
        ancestor = parentStack->Index(1);

        switch (ancestor->OperGet())
        {
        case GT_EQ:
        case GT_NE:
        case GT_IND:
            canLclVarEscapeViaParentStack = false; // Scenario (1)
            break;

        case GT_ADD:
            if (parentStack->Height() > 2)
            {
                ancestor = parentStack->Index(2);

                switch (ancestor->OperGet())
                {
                case GT_IND:
                    canLclVarEscapeViaParentStack = false; // Scenario (2)
                    break;
                default:
                    break;
                }
            }
            break;

        case GT_CALL:
            {
                GenTreeCall* asCall = ancestor->AsCall();
                
                if (asCall->gtCallType == CT_HELPER)
                {
                    const CorInfoHelpFunc helperNum = compiler->eeGetHelperNum(asCall->gtCallMethHnd);

                    if (Compiler::s_helperCallProperties.IsPure(helperNum))
                    {
                        canLclVarEscapeViaParentStack = false; // Scenario (3)
                    }
                }
            }
            break;
        default:
            break;
        }
    }

    return canLclVarEscapeViaParentStack;
}

#ifdef DEBUG

//------------------------------------------------------------------------
// AssertWhenAllocObjFoundVisitor: Look for a GT_ALLOCOBJ node and assert
//                                 when found one.
//
// Arguments:
//    pTree - 
//    data  - 
Compiler::fgWalkResult ObjectAllocator::AssertWhenAllocObjFoundVisitor(GenTreePtr* pTree, Compiler::fgWalkData* data)
{
    GenTreePtr tree = *pTree;

    assert(tree != nullptr);
    assert(tree->OperGet() != GT_ALLOCOBJ);

    return Compiler::fgWalkResult::WALK_CONTINUE;
}

#endif // DEBUG

//===============================================================================
