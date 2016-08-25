// Licensed to the .NET Foundation under one or more agreements.
// The .NET Foundation licenses this file to you under the MIT license.
// See the LICENSE file in the project root for more information.

/*XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
XX                                                                           XX
XX                    TarjanStronglyConnectedComponents                      XX
XX                                                                           XX
XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
*/

#include "jitpch.h"
#ifdef _MSC_VER
#pragma hdrstop
#endif

//===============================================================================

void TarjanStronglyConnectedComponents::DoAnalysis()
{
    assert(!m_IsAnalysisDone);

    BasicBlock* block;

    foreach_block(m_Compiler, block)
    {
        // If block is not yet visited
        if (m_InvalidNumber == m_Number[block->bbNum])
        {
            StrongConnect(block);
        }
    }

    m_IsAnalysisDone = true;
}

void TarjanStronglyConnectedComponents::StrongConnect(BasicBlock* block)
{
    const unsigned int thisNum = block->bbNum;
    m_Number[thisNum]          = m_SmallestUnusedNumber;
    m_LowLink[thisNum]         = m_SmallestUnusedNumber;
    m_SmallestUnusedNumber     = m_SmallestUnusedNumber + 1;

    m_Stack.Push(thisNum);
    BitVecOps::AddElemD(&m_BitVecTraits, m_IsOnStack, thisNum);

    const unsigned int numSucc = block->NumSucc(m_Compiler);

    for (unsigned int i = 0; i < numSucc; ++i)
    {
        BasicBlock*  succ    = block->GetSucc(i, m_Compiler);
        unsigned int succNum = succ->bbNum;

        // If succ is not yet visited
        if (m_InvalidNumber == m_Number[succNum])
        {
            StrongConnect(succ);

            if (m_LowLink[succNum] < m_LowLink[thisNum])
            {
                m_LowLink[thisNum] = m_LowLink[succNum];
            }

            assert(m_LowLink[thisNum] == min(m_LowLink[thisNum], m_LowLink[succNum]));
        }
        else if (m_Number[succNum] < m_Number[thisNum])
        {
            const bool isSuccOnStack = BitVecOps::IsMember(&m_BitVecTraits, m_IsOnStack, succNum);

            if (isSuccOnStack)
            {
                if (m_Number[succNum] < m_LowLink[thisNum])
                {
                    m_LowLink[thisNum] = m_Number[succNum];
                }

                assert(m_LowLink[thisNum] == min(m_LowLink[thisNum], m_Number[succNum]));
            }
        }

        if (thisNum == succNum)
        {
            BitVecOps::AddElemD(&m_BitVecTraits, m_IsPartOfCycle, thisNum);
        }
    }

    if (m_LowLink[thisNum] == m_Number[thisNum])
    {
        unsigned int topNum        = m_Stack.Top();
        const bool   isPartOfCycle = (topNum != thisNum);

        do
        {
            topNum = m_Stack.Pop();
            BitVecOps::RemoveElemD(&m_BitVecTraits, m_IsOnStack, topNum);

            if (isPartOfCycle)
            {
                BitVecOps::AddElemD(&m_BitVecTraits, m_IsPartOfCycle, topNum);
            }

            assert(m_Number[topNum] >= m_Number[thisNum]);
        } while (m_Number[topNum] > m_Number[thisNum]);
    }
}
