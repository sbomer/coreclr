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

/*****************************************************************************/
#ifndef TARJANSCC_H
#define TARJANSCC_H
/*****************************************************************************/

//===============================================================================

class TarjanStronglyConnectedComponents
{
    //===============================================================================
    // Data members
    Compiler* const              m_Compiler;
    const unsigned int           m_InvalidNumber;
    bool                         m_IsAnalysisDone;
    BitVecTraits                 m_BitVecTraits;
    BitVec                       m_IsOnStack;
    BitVec                       m_IsPartOfCycle;
    ArrayStack<unsigned int>     m_Stack;
    jitstd::vector<unsigned int> m_LowLink;
    jitstd::vector<unsigned int> m_Number;
    unsigned int                 m_SmallestUnusedNumber;

    //===============================================================================
    // Methods
public:
    TarjanStronglyConnectedComponents(Compiler* compiler);
    void DoAnalysis();
    bool IsPartOfCycle(unsigned int bbNum);

private:
    void StrongConnect(BasicBlock* block);
};

//===============================================================================

inline TarjanStronglyConnectedComponents::TarjanStronglyConnectedComponents(Compiler* compiler)
    : m_Compiler(compiler), m_InvalidNumber(0), m_BitVecTraits(compiler->fgBBcount + 1, compiler),
      m_Stack(compiler, compiler->fgBBcount),
      m_Number(compiler->fgBBcount + 1, m_InvalidNumber, compiler->getAllocator()),
      m_LowLink(compiler->fgBBcount + 1, m_InvalidNumber, compiler->getAllocator())
{
    m_IsAnalysisDone       = false;
    m_IsOnStack            = BitVecOps::MakeEmpty(&m_BitVecTraits);
    m_IsPartOfCycle        = BitVecOps::MakeEmpty(&m_BitVecTraits);
    m_SmallestUnusedNumber = m_InvalidNumber + 1;
}

inline bool TarjanStronglyConnectedComponents::IsPartOfCycle(unsigned int bbNum)
{
    assert(m_IsAnalysisDone);
    return BitVecOps::IsMember(&m_BitVecTraits, m_IsPartOfCycle, bbNum);
}

//===============================================================================

#endif // TARJANSCC_H
