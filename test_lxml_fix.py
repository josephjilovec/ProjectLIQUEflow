"""
Test script to verify the lxml encoding fix works correctly.
This tests that XML generation no longer throws ValueError.
"""

import sys
from src.message_generator.iso20022_generator import ISO20022Generator
from src.utils.models import PriorityTier

def test_pacs008_generation():
    """Test pacs.008 message generation."""
    print("Testing pacs.008 generation...")
    generator = ISO20022Generator()
    
    try:
        message = generator.generate_pacs008(
            amount=1000000.0,
            priority=PriorityTier.URGENT,
            is_sovereign=True
        )
        
        # Verify XML was generated
        assert message.raw_xml is not None, "XML should not be None"
        assert "<?xml" in message.raw_xml, "XML should contain declaration"
        assert "pacs.008" in message.raw_xml or "FIToFICstmrCdtTrf" in message.raw_xml, "XML should contain pacs.008 elements"
        
        print("✅ pacs.008 generation: PASSED")
        print(f"   Generated XML length: {len(message.raw_xml)} characters")
        return True
        
    except ValueError as e:
        print(f"❌ pacs.008 generation: FAILED - {e}")
        return False
    except Exception as e:
        print(f"❌ pacs.008 generation: FAILED - Unexpected error: {e}")
        return False

def test_camt053_generation():
    """Test camt.053 message generation."""
    print("\nTesting camt.053 generation...")
    generator = ISO20022Generator()
    
    try:
        message = generator.generate_camt053(current_balance=1000000000.0)
        
        # Verify XML was generated
        assert message.raw_xml is not None, "XML should not be None"
        assert "<?xml" in message.raw_xml, "XML should contain declaration"
        assert "camt.053" in message.raw_xml or "BkToCstmrStmt" in message.raw_xml, "XML should contain camt.053 elements"
        
        print("✅ camt.053 generation: PASSED")
        print(f"   Generated XML length: {len(message.raw_xml)} characters")
        return True
        
    except ValueError as e:
        print(f"❌ camt.053 generation: FAILED - {e}")
        return False
    except Exception as e:
        print(f"❌ camt.053 generation: FAILED - Unexpected error: {e}")
        return False

def test_multiple_generations():
    """Test generating multiple messages (like in scenarios)."""
    print("\nTesting multiple message generation...")
    generator = ISO20022Generator()
    
    try:
        messages = []
        for i in range(10):
            message = generator.generate_pacs008(
                amount=1000000.0 * (i + 1),
                priority=PriorityTier.NORMAL
            )
            messages.append(message)
        
        assert len(messages) == 10, "Should generate 10 messages"
        assert all(msg.raw_xml is not None for msg in messages), "All messages should have XML"
        
        print("✅ Multiple generation: PASSED")
        print(f"   Generated {len(messages)} messages successfully")
        return True
        
    except Exception as e:
        print(f"❌ Multiple generation: FAILED - {e}")
        return False

def main():
    """Run all tests."""
    print("=" * 60)
    print("Project Lique-Flow: lxml Encoding Fix Verification")
    print("=" * 60)
    print()
    
    results = []
    results.append(test_pacs008_generation())
    results.append(test_camt053_generation())
    results.append(test_multiple_generations())
    
    print()
    print("=" * 60)
    if all(results):
        print("✅ ALL TESTS PASSED - lxml fix is working correctly!")
        print()
        print("The fix ensures:")
        print("  • XML is generated as UTF-8 bytes first")
        print("  • Then decoded to string (avoiding ValueError)")
        print("  • XML declaration is properly included")
        return 0
    else:
        print("❌ SOME TESTS FAILED - Please check the errors above")
        return 1

if __name__ == "__main__":
    sys.exit(main())

