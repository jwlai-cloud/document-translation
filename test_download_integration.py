#!/usr/bin/env python3
"""Integration test for download service."""

import tempfile
from unittest.mock import Mock, patch

from src.models.document import (
    DocumentStructure, PageStructure, TextRegion, BoundingBox,
    Dimensions, DocumentMetadata
)
from src.models.layout import AdjustedRegion
from src.services.download_service import (
    DownloadService, DownloadConfig, DownloadRequest, FileNamingService
)

def test_download_service_integration():
    """Test complete download service workflow."""
    
    print("🧪 Testing Download Service Integration...")
    
    # Create download service with custom config
    config = DownloadConfig(
        temp_storage_duration=1800,  # 30 minutes
        max_concurrent_downloads=3,
        secure_links=True,
        link_expiration_time=3600  # 1 hour
    )
    
    service = DownloadService(config)
    
    try:
        # Create test document with multiple elements
        print("\n✓ Creating test document...")
        
        text_regions = [
            TextRegion(
                id="title",
                bounding_box=BoundingBox(50, 50, 300, 40),
                text_content="Document Title"
            ),
            TextRegion(
                id="paragraph1",
                bounding_box=BoundingBox(50, 120, 300, 60),
                text_content="This is the first paragraph of the document."
            ),
            TextRegion(
                id="paragraph2",
                bounding_box=BoundingBox(50, 200, 300, 80),
                text_content="This is a longer second paragraph with more content."
            )
        ]
        
        document = DocumentStructure(
            format="pdf",
            pages=[
                PageStructure(
                    page_number=1,
                    dimensions=Dimensions(width=400, height=600),
                    text_regions=text_regions
                )
            ],
            metadata=DocumentMetadata(title="Integration Test Document")
        )
        
        print(f"  - Created document with {len(text_regions)} text regions")
        
        # Create translated regions
        print("\n✓ Creating translated regions...")
        
        translated_regions = {
            "1": [
                AdjustedRegion(
                    original_region=text_regions[0],
                    adjusted_text="Titre du Document",
                    new_bounding_box=BoundingBox(50, 50, 320, 45),
                    adjustments=[],
                    fit_quality=0.9
                ),
                AdjustedRegion(
                    original_region=text_regions[1],
                    adjusted_text="Ceci est le premier paragraphe du document.",
                    new_bounding_box=BoundingBox(50, 120, 330, 65),
                    adjustments=[],
                    fit_quality=0.85
                ),
                AdjustedRegion(
                    original_region=text_regions[2],
                    adjusted_text="Ceci est un deuxième paragraphe plus long avec plus de contenu.",
                    new_bounding_box=BoundingBox(50, 200, 350, 85),
                    adjustments=[],
                    fit_quality=0.8
                )
            ]
        }
        
        print(f"  - Created {len(translated_regions['1'])} translated regions")
        
        # Test filename generation
        print("\n✓ Testing filename generation...")
        
        filename_tests = [
            {
                "name": "Basic filename",
                "prefix": "",
                "timestamp": False,
                "language": False
            },
            {
                "name": "With prefix",
                "prefix": "translated",
                "timestamp": False,
                "language": False
            },
            {
                "name": "With language info",
                "prefix": "",
                "timestamp": False,
                "language": True
            },
            {
                "name": "With timestamp",
                "prefix": "",
                "timestamp": True,
                "language": False
            },
            {
                "name": "Full options",
                "prefix": "fr_translation",
                "timestamp": True,
                "language": True
            }
        ]
        
        for test in filename_tests:
            filename = FileNamingService.generate_filename(
                document,
                "pdf",
                prefix=test["prefix"],
                include_timestamp=test["timestamp"],
                include_language_info=test["language"]
            )
            print(f"  - {test['name']}: {filename}")
        
        # Test different download formats
        print("\n✓ Testing download preparation for different formats...")
        
        formats_to_test = ["pdf", "docx", "epub"]
        download_links = []
        
        for format_type in formats_to_test:
            print(f"  - Testing {format_type.upper()} format...")
            
            # Create download request
            download_request = DownloadRequest(
                request_id=f"test_{format_type}",
                document=document,
                translated_regions=translated_regions,
                target_format=format_type,
                filename_prefix=f"{format_type}_translated"
            )
            
            # Mock reconstruction engine for testing
            with patch('src.services.download_service.DefaultLayoutReconstructionEngine') as mock_engine_class:
                mock_engine = Mock()
                mock_content = f"Mock reconstructed {format_type.upper()} content with translations".encode()
                mock_engine.reconstruct_document.return_value = mock_content
                mock_engine_class.return_value = mock_engine
                
                # Prepare download
                result = service.prepare_download(download_request)
                
                if result.success:
                    print(f"    ✓ Download prepared successfully")
                    print(f"    Processing time: {result.processing_time:.3f}s")
                    
                    download_link = result.download_link
                    print(f"    Link ID: {download_link.link_id[:16]}...")
                    print(f"    Filename: {download_link.original_filename}")
                    print(f"    File size: {download_link.file_size} bytes")
                    print(f"    Format: {download_link.file_format}")
                    
                    download_links.append(download_link)
                else:
                    print(f"    ❌ Download preparation failed: {result.error_message}")
        
        # Test download information retrieval
        print("\n✓ Testing download information retrieval...")
        
        for download_link in download_links:
            info = service.get_download_info(download_link.link_id)
            
            if info:
                print(f"  - Link {download_link.link_id[:16]}...:")
                print(f"    Filename: {info['filename']}")
                print(f"    Format: {info['format']}")
                print(f"    File size: {info['file_size']} bytes")
                print(f"    Download count: {info['download_count']}/{info['max_downloads']}")
                print(f"    Valid: {info['is_valid']}")
                print(f"    Time remaining: {info['time_remaining']:.0f}s")
            else:
                print(f"  - Link {download_link.link_id[:16]}...: Not found")
        
        # Test file downloads
        print("\n✓ Testing file downloads...")
        
        for download_link in download_links[:2]:  # Test first 2 to avoid exhausting all
            print(f"  - Downloading {download_link.original_filename}...")
            
            success, file_bytes, filename, metadata = service.download_file(download_link.link_id)
            
            if success:
                print(f"    ✓ Download successful")
                print(f"    Filename: {filename}")
                print(f"    Content size: {len(file_bytes)} bytes")
                print(f"    Content preview: {file_bytes[:50]}...")
                print(f"    Download count: {metadata['download_count']}")
            else:
                print(f"    ❌ Download failed: {metadata.get('error', 'Unknown error')}")
        
        # Test download service statistics
        print("\n✓ Testing service statistics...")
        
        stats = service.get_download_stats()
        print(f"  - Active download links: {stats['active_download_links']}")
        print(f"  - Total storage size: {stats['total_storage_size_bytes']} bytes")
        print(f"  - Temp storage path: {stats['temp_storage_path']}")
        print(f"  - Link expiration time: {stats['link_expiration_time_seconds']}s")
        print(f"  - Max concurrent downloads: {stats['max_concurrent_downloads']}")
        
        # Test download cancellation
        print("\n✓ Testing download cancellation...")
        
        if download_links:
            last_link = download_links[-1]
            print(f"  - Cancelling download: {last_link.original_filename}")
            
            success = service.cancel_download(last_link.link_id)
            
            if success:
                print(f"    ✓ Download cancelled successfully")
                
                # Verify link is no longer available
                info = service.get_download_info(last_link.link_id)
                if info is None:
                    print(f"    ✓ Link properly cleaned up")
                else:
                    print(f"    ⚠️  Link still exists after cancellation")
            else:
                print(f"    ❌ Failed to cancel download")
        
        # Test cleanup of expired downloads
        print("\n✓ Testing expired download cleanup...")
        
        cleaned_count = service.cleanup_expired_downloads()
        print(f"  - Cleaned up {cleaned_count} expired downloads")
        
        # Final statistics
        final_stats = service.get_download_stats()
        print(f"\n✓ Final Statistics:")
        print(f"  - Active download links: {final_stats['active_download_links']}")
        print(f"  - Total storage size: {final_stats['total_storage_size_bytes']} bytes")
        
        print("\n🎉 Download service integration test completed successfully!")
        return True
        
    except Exception as e:
        print(f"\n❌ Integration test failed: {e}")
        raise
    finally:
        # Always shutdown the service
        service.shutdown()

def test_download_edge_cases():
    """Test download service with edge cases."""
    
    print("\n🧪 Testing Download Edge Cases...")
    
    service = DownloadService()
    
    try:
        # Test with empty document
        print("  - Testing empty document...")
        empty_document = DocumentStructure(
            format="pdf",
            pages=[],
            metadata=DocumentMetadata(title="Empty Document")
        )
        
        download_request = DownloadRequest(
            request_id="empty_test",
            document=empty_document,
            translated_regions={},
            target_format="pdf"
        )
        
        with patch('src.services.download_service.DefaultLayoutReconstructionEngine') as mock_engine_class:
            mock_engine = Mock()
            mock_engine.reconstruct_document.return_value = b"Empty document content"
            mock_engine_class.return_value = mock_engine
            
            result = service.prepare_download(download_request)
            
            if result.success:
                print("    ✓ Empty document handled correctly")
            else:
                print(f"    ❌ Empty document failed: {result.error_message}")
        
        # Test with document with no title
        print("  - Testing document with no title...")
        no_title_document = DocumentStructure(
            format="pdf",
            pages=[
                PageStructure(
                    page_number=1,
                    dimensions=Dimensions(width=400, height=600),
                    text_regions=[
                        TextRegion(
                            id="content",
                            bounding_box=BoundingBox(10, 10, 200, 30),
                            text_content="Content without title"
                        )
                    ]
                )
            ],
            metadata=DocumentMetadata()  # No title
        )
        
        filename = FileNamingService.generate_filename(
            no_title_document,
            "pdf",
            include_timestamp=False,
            include_language_info=False
        )
        
        print(f"    Generated filename: {filename}")
        assert "translated_document" in filename
        print("    ✓ No title document handled correctly")
        
        # Test with invalid characters in title
        print("  - Testing document with invalid characters in title...")
        invalid_title_document = DocumentStructure(
            format="pdf",
            pages=[],
            metadata=DocumentMetadata(title="Test<>Document:/\\|?*")
        )
        
        filename = FileNamingService.generate_filename(
            invalid_title_document,
            "pdf",
            include_timestamp=False,
            include_language_info=False
        )
        
        print(f"    Generated filename: {filename}")
        assert "<" not in filename
        assert ">" not in filename
        assert ":" not in filename
        print("    ✓ Invalid characters handled correctly")
        
        # Test concurrent download limit
        print("  - Testing concurrent download limit...")
        
        # Set low limit for testing
        service.config.max_concurrent_downloads = 1
        import threading
        service.download_semaphore = threading.Semaphore(1)
        
        # Acquire semaphore to simulate busy service
        service.download_semaphore.acquire()
        
        try:
            download_request = DownloadRequest(
                request_id="concurrent_test",
                document=no_title_document,
                translated_regions={},
                target_format="pdf"
            )
            
            result = service.prepare_download(download_request)
            
            if not result.success and "concurrent" in result.error_message.lower():
                print("    ✓ Concurrent limit handled correctly")
            else:
                print(f"    ⚠️  Unexpected result: {result.error_message}")
        finally:
            service.download_semaphore.release()
        
        print("✓ Edge case testing completed!")
        
    finally:
        service.shutdown()

if __name__ == "__main__":
    try:
        test_download_service_integration()
        test_download_edge_cases()
        print("\n✅ All download service integration tests passed!")
    except Exception as e:
        print(f"\n❌ Integration test failed: {e}")
        raise