import base64
import io
import zlib
import struct

def parse_and_modify_push_request(base64_data, new_commit_field):
    """
    Parses a Git push request, extracts the PACK data, modifies the commit field, 
    and re-encodes the request.

    Args:
        base64_data (str): Base64-encoded Git push request.
        new_commit_field (str): New value for the "Commit" field.

    Returns:
        str: The modified Git push request, base64-encoded.
    """
    # Step 1: Decode the base64-encoded push request
    binary_data = base64.b64decode(base64_data)
    request_stream = io.BytesIO(binary_data)

    # Step 2: Locate the PACK section in the request
    pack_start = binary_data.find(b'PACK')
    if pack_start == -1:
        raise ValueError("PACK section not found in the push request")

    # Split the metadata and PACK data
    metadata = binary_data[:pack_start]
    packfile_data = binary_data[pack_start:]

    # Step 3: Parse the PACK file
    packfile_stream = io.BytesIO(packfile_data)
    modified_packfile = io.BytesIO()

    # Read the PACK header
    magic = packfile_stream.read(4)
    if magic != b'PACK':
        raise ValueError("Invalid PACK file format")

    # Write the magic string to the modified packfile
    modified_packfile.write(magic)

    # Read the version and number of objects
    version = struct.unpack(">I", packfile_stream.read(4))[0]
    num_objects = struct.unpack(">I", packfile_stream.read(4))[0]
    modified_packfile.write(struct.pack(">I", version))
    modified_packfile.write(struct.pack(">I", num_objects))

    print(f"PACK file version: {version}, Number of objects: {num_objects}")

    # Process each object in the PACK file
    for _ in range(num_objects):
        object_type, object_size = parse_object_header(packfile_stream)
        compressed_data = decompress_object(packfile_stream)
        object_data = zlib.decompress(compressed_data)

        # Modify commit objects
        if object_type == 1:  # Commit object
            object_data = modify_commit_object(object_data, new_commit_field)

        # Recompress the modified object data
        compressed_data = zlib.compress(object_data)

        # Write the object header and data to the modified packfile
        write_object_header(modified_packfile, object_type, len(object_data))
        modified_packfile.write(compressed_data)

    # Calculate and write the checksum
    checksum = calculate_checksum(modified_packfile.getvalue())
    modified_packfile.write(checksum)

    # Step 4: Reassemble the push request
    modified_request = metadata + modified_packfile.getvalue()

    # Step 5: Re-encode the push request as base64
    return base64.b64encode(modified_request).decode()


def parse_object_header(stream):
    """
    Parse the object header in the PACK file.
    """
    first_byte = ord(stream.read(1))
    object_type = (first_byte >> 4) & 0b111
    size = first_byte & 0b1111

    shift = 4
    while first_byte & 0b10000000:  # Continuation bit
        first_byte = ord(stream.read(1))
        size |= (first_byte & 0b01111111) << shift
        shift += 7

    return object_type, size


def decompress_object(stream):
    """
    Decompress an object from the PACK file.
    """
    decompressor = zlib.decompressobj()
    compressed_data = b''

    while True:
        chunk = stream.read(8192)
        if not chunk:
            break
        compressed_data += chunk
        try:
            decompressor.decompress(chunk)
        except zlib.error:
            break

    return compressed_data


def modify_commit_object(object_data, new_commit_field):
    """
    Modify the commit object to update the 'Commit' field.
    """
    object_str = object_data.decode("utf-8")
    if "Commit: " in object_str:
        object_str = object_str.replace("Commit: GitHub <noreply@github.com>", f"Commit: {new_commit_field}")
    return object_str.encode("utf-8")


def write_object_header(stream, object_type, size):
    """
    Write the object header (type and size) to the PACK file.
    """
    header = (object_type << 4) | (size & 0b1111)
    size >>= 4

    while size:
        header |= 0b10000000
        stream.write(struct.pack("B", header))
        header = size & 0b1111111
        size >>= 7

    stream.write(struct.pack("B", header))


def calculate_checksum(data):
    """
    Calculate the SHA-1 checksum for the PACK file.
    """
    import hashlib
    return hashlib.sha1(data).digest()


# Example usage
if __name__ == "__main__":
    # Replace with your base64-encoded Git push request
    base64_encoded_push_request = "MDBiMzU4YjExMjNlNDNjNjI5NTQyY2NmMTJlYTQ5Njc5NGU0ODViNjNlOGIgNmNlMDk5ZGEzZTViMTVhNWY4ODJkNjA0ZjUyM2ZmNzIwYzI3NGE4MiByZWZzL2hlYWRzL21haW4AIHJlcG9ydC1zdGF0dXMtdjIgc2lkZS1iYW5kLTY0ayBvYmplY3QtZm9ybWF0PXNoYTEgYWdlbnQ9Z2l0LzIuNDUuMS53aW5kb3dzLjEwMDAwUEFDSwAAAAIAAAADkxF4nK3MPW4DIRRF4Z5V0Fse8fN4gGRFKd1kEcDcMZaMsRim8O4dZQ1pzyedOQDJ5DNohd04JTBH6FXbQkVtmf0WQgFr5CJeaeA5pQtZa2NBtrCJjkwpmzZIFNlHAgWX2SJkkY5Z+5DXtFc0+dNraljlRSvPFGzkU/2Tc+vfx46xL88+8Hq8l9t91iMvpbcvqb31ztkYojwpo5T4re0+J/59LCb2KT5NVFQz/QLNhAMs+QtRRcu+2IlK2FLIivBgqXicm894lFHN0MDAzMREITkxObWoRK8gNZfh3rQzMYej9rz82hHR6OtZf8SH8fuNCfMBfPATlr5SeJx9lEuTqjoURuf8ijunukBAGoYJBIwQMLxUZijKU0QFefz6Y/epe25X96mbUWrvqlVfrZ3st7fXgcjEzj8a8gJsYA0E6KP4xhCM9XbWNHBlMzBgCDKMdC9NlBI4MKtueVWY6sBDQB8G0DVYlCgkEJtgESKYE5sJTXVKDUdMtmkT7/Bo6MCHmRO9SIG2gM9j4wWpUDexEE3EowPK9npE6QoNHT2Ia54JxbSNhbQ+fiFrL/IP8Ayi3+BHoNf/gZkPMkYOJN5xMOgnXUfD8pP+B15AnQbgZAz86OhAIOV+IAGYSAkT5lWcvxcJNq0vcc1/4/4tLaPBv8T94+H4fx6sDzDzjbwjMPztYSTuN3BGefTFBfl0wXylf7rAGOIfI0QGAK4GqAI++lpmve4ItJyDGDM7kDl4Uo2ybbJpVsocmtEmDcs96uSds84kcjGJTDklmZPyadHYWYvzoUJn2bhIY8ocD562XbrChAOx2nrAleWDdOCVBZes87Q/dkpF3P3dvybdxajOhR1NUg2CXCVTeaLjliG7OuiXnrVBPDk+NkZkCMa2pV2367kyCH1NnU8cd3IuxPLioZNYS7KE1EiBbZdDfMqZxenahqvRiEf0BFUfhsqDU/aHfaVoxhNF/SjkKu8olUZ3o+onfCqnbM9jcym/69xc7JhbkgtXO2FFi+NpLob1etWIKy8WiLqPqLAoKn8VIHlsVsvOwNB7ktVUB5fmNPfvyXbuGIsPl8B59G3Fi4PCy9yAdUABvI5kQAHYfIxs5REIzgqCAXj1VhwBvKn5N9PHB5HRKYLaEAIgvX4ihTSZXF08PkgWxNz2LgHWVwyp2y0nm513+tRsHoW3sLU9bjjWc70Fk7U7gXPX9gAX19V93Br2k4NXu/WbRTZeQatqmdAcCzO7TOq0QCf5mQ+W59WXBcLmc7lk1oNf0gpdcs7Fu+losHdBbrdOcIMSvm/ECyyXlSh3MM5EmubieBFc1b/LATe6TeeXAePW62leeyodXGfwTxH7TuQH2urSrZ+dx6CWoruqn5JcIIHH9mNZgySvjYjVffvm4dJmhKx7mtFt3ZWZeO+3oHgvsl49u3XhG7gL1at5GZ0NNns5Pxe3aGGQ5VnZCxpb6E4vcTEj1y5gh2tcTfzrBb/LrfV8Jxu4oTXd7PeN5D+MhvncfsjRf27EX2sJpBo82DjtRQG3mLV5zKTEO65VZOVLSQ=="

    # Replace with the new commit field value
    new_commit_field = "GitHub <noreply@github.com>"

    try:
        modified_push_request = parse_and_modify_push_request(base64_encoded_push_request, new_commit_field)
        print("Modified Push Request (Base64):")
        print(modified_push_request)
    except Exception as e:
        print(f"Error: {e}")
